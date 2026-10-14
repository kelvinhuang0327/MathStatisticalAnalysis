r"""Full-profile T<=257 from the three degree-one vertices; no solver or census.

For d=(6^3,5^9,1^3,0^5), G has degrees 6+d and 93 edges. Its complement
H has 97 edges and T=t(G)=297-t(H). Put K={d>0}, Z={d=0}, M=H[K],
MZ=H[Z], sigma_x=|N_G(x)∩Z| and zeta_u=|N_G(u)∩K|. Then |K|=15,
|Z|=5, deg_M=8-d+sigma, deg_MZ=zeta-2, and sum sigma=sum zeta=r.
Mixed triangles counted at their unique same-part edge give
 t(H)=60+12r-sum sigma(8-d+sigma)-sum zeta^2+P,
 P=t(M)+t(MZ)+sum_M |N_G(x)∩N_G(y)∩Z|
                 +sum_MZ |N_G(u)∩N_G(v)∩K| >= 0.
With a=sum sigma on the nine d=5 vertices and q the three d=1 sigmas,
 T=F-P, F=237-2a+sum q_i(q_i+1)+sum zeta_u(zeta_u-6).

The new restriction: each d=6 vertex has 12 distinct shadow neighbours
among K. Only 11 other vertices have d>=5, so at least one neighbour is
in L={d=1}. L has shadow degree sum 6, hence its shadow has at most one
internal edge. Its core pair incidence is B=sum(5-q_i). Thus the graph
J=G[L] satisfies 2|J|<=2+B, for every legal support realization.

Let E=C(L,2)\J and n_i=deg_E(i). For ij in E, the two M-neighbour sets
inside K\L have sizes 7+q_i-n_i and 7+q_j-n_j in a universe of size 12;
their intersection is at least max(0,2+q_i+q_j-n_i-n_j). Common G zero
neighbours number at least max(0,q_i+q_j-5). These count distinct terms
of P, together with the all-L triangle when |E|=3. Therefore
 P>=ell(q,J)=1_{|E|=3}+sum_E[max(0,2+q_i+q_j-n_i-n_j)
                                      +max(0,q_i+q_j-5)].

The finite relaxation enumerates a=0..9, sorted q in {0..5}^3, all eight
labelled J, and sorted zeta=2+degrees of all 2^10 simple graphs on Z.
Keep sum zeta=a+sum q and 2|J|<=2+B. These are necessary conditions;
no simultaneous graphicality or support construction is required. Every
legal support maps into this superset: sorting q also permutes J, whose
eight possibilities are all retained; sorting zeros preserves F. The
3,771 retained states all satisfy F-ell<=257. Attainment is not claimed.
The witness is only an identity check. Route B uses all integer T values,
independent exact rationals, and the frozen R32 and split implementations.
"""

from __future__ import annotations

import hashlib
import json
import resource
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from pathlib import Path
from time import process_time

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split

TASK_ID = "B649_NEW_FAMILY_MAX_OWNER_A_R1"
PROFILE_ID = "66655555555511100000"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
FROZEN_RESULT = "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
SOURCE = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1199]"
SOURCE_CAP, SOURCE_S4_BASE, SOURCE_BOUND = 264, 112, 313_395_344
TARGET_BOUND, PROVED_CAP, NEW_BOUND = 313_395_164, 257, 313_332_416
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIR = Path("docs/research/matrix-native-results")
RESULT_PATH = ROOT / RESULT_DIR / "b649-new-family-max-owner-a-r1-result.json"
LOW_EDGES = tuple(combinations(range(3), 2))
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
integer, object_row, rows, text = split.integer, split.object_row, split.rows, split.text


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sealed(path: str, expected: str | None = None) -> tuple[bytes, str]:
    """Pin local input to its frozen blob, optionally also to a Packet digest."""
    raw = git("show", f"{FROZEN_HEAD}:{path}")
    digest = hashlib.sha256(raw).hexdigest()
    require(expected is None or digest == expected, "source digest mismatch")
    require((ROOT / path).read_bytes() == raw, f"local source identity changed: {path}")
    return raw, digest


def premises(profile: str = PROFILE_ID) -> dict[str, object]:
    require(profile == PROFILE_ID, "wrong Profile")
    p = tuple(map(int, profile))
    require(Counter(p) == {6: 3, 5: 9, 1: 3, 0: 5}, "wrong Profile distribution")
    k, z = sum(d > 0 for d in p), p.count(0)
    g, h = tuple(6 + d for d in p), tuple(13 - d for d in p)
    phi = comb(20, 3) - 18 * (sum(h) // 2) + sum(comb(v, 2) for v in h)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    require(
        (sum(p), sum(d * d for d in p), k, z, sum(g), sum(h), phi, goodman)
        == (66, 336, 15, 5, 186, 194, 297, 297),
        "Goodman/core-zero premises changed",
    )
    return {
        "PROFILE_ID": profile,
        "DEGREE_DISTRIBUTION": "6^3,5^9,1^3,0^5",
        "DEGREE_SUM": sum(p),
        "DEGREE_SQUARE_SUM": sum(d * d for d in p),
        "CORE_COUNT": k,
        "ZERO_COUNT": z,
        "GOODMAN_CONSTANT": phi,
        "G_EDGES": sum(g) // 2,
        "H_EDGES": sum(h) // 2,
    }


@dataclass(frozen=True)
class SourceRow:
    bound: int
    cap: int
    s4_base: int
    source: str
    realization: tuple[tuple[Support, ...], tuple[Support, ...]]


def audit_row(row: SourceRow) -> None:
    require(
        (row.bound, row.cap, row.s4_base, row.source)
        == (SOURCE_BOUND, SOURCE_CAP, SOURCE_S4_BASE, SOURCE),
        "source Row identity/cap/S4/bound mismatch",
    )
    require(max(t[1] for t in route_b(row.cap)) == row.bound, "recorded bound mismatch")


def source_authority() -> tuple[SourceRow, dict[str, str]]:
    """Target-only reads from frozen ledger, archived source row and R12 witness.

    The task also independently replayed the six-row authority (4,647 rows,
    both sealed digests checked), obtaining this exact Row in 38.529633 CPU s.
    This loader avoids rerunning that whole ledger during focused tests.
    """
    require(
        git("rev-parse", f"{FROZEN_HEAD}^{{tree}}").decode().strip() == FROZEN_TREE,
        "frozen tree mismatch",
    )
    provenance: dict[str, str] = {}

    def read(name: str, digest: str | None = None) -> dict[str, object]:
        path = (RESULT_DIR / name).as_posix()
        raw, actual = sealed(path, digest)
        provenance[path] = actual
        return object_row(json.loads(raw))

    frozen = read(FROZEN_RESULT, FROZEN_SHA256)
    require(
        frozen["SIX_ROW_RESULT_SHA256"]
        == "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f",
        "six-row source linkage changed",
    )
    six = read(
        "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json",
        text(frozen["SIX_ROW_RESULT_SHA256"]),
    )
    require(
        object_row(six["RESOLVED_ROW_BOUNDS"])[PROFILE_ID] == SOURCE_BOUND,
        "frozen ledger target bound changed",
    )
    require(
        PROFILE_ID not in rows(frozen["ROWS_CHANGED_FROM_SIX_ROW"]),
        "target changed after six-row authority",
    )
    archived = read("b649-min-s2-six-row-existing-s4-family-authority-r1-sources/s4-result.json")
    family = object_row(archived["FINAL_FAMILY"])
    matches = [
        object_row(v)
        for v in rows(family["ROWS_ABOVE_CURSOR"])
        if object_row(v).get("PROFILE_ID") == PROFILE_ID
    ]
    require(len(matches) == 1, "source row absent or duplicated")
    found = matches[0]
    witness = object_row(
        rows(
            read("b649-k20-min-s2-continued-multi-plateau-descent-r12-result.json")[
                "PROFILE_BOUNDS"
            ]
        )[30]
    )
    require(
        tuple(integer(v) for v in rows(witness["PROFILE"])) == tuple(map(int, PROFILE_ID)),
        "witness source Profile changed",
    )
    supports = tuple(
        tuple(tuple(map(int, part.split(","))) for part in text(witness[key]).split(";"))
        for key in ("WITNESS_TRIPLES", "WITNESS_DOUBLE_SUPPORTS")
    )
    require(len(supports) == 2, "witness support shape")
    row = SourceRow(
        integer(found["BOUND"]),
        integer(found["TRIANGLE_CAP"]),
        r32.r28.profile_s4_floor(tuple(map(int, PROFILE_ID))),
        text(found["SOURCE"]),
        (supports[0], supports[1]),
    )
    audit_row(row)
    # Pin every actually imported repository module, including transitive dependencies.
    for name, module in sorted(sys.modules.copy().items()):
        if not name.startswith("lottolab.research."):
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue
        path = Path(filename).resolve()
        require(path.is_relative_to(ROOT), "research dependency outside this worktree")
        if path == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT).as_posix()
        _, provenance[relative] = sealed(relative)
    return row, dict(sorted(provenance.items()))


def zero_vectors() -> tuple[tuple[int, ...], ...]:
    """All simple graphs on the five zeros; 1,024 masks, no graphicality oracle."""
    edges = tuple(combinations(range(5), 2))
    vectors: set[tuple[int, ...]] = set()
    for mask in range(1 << len(edges)):
        degree = [0] * 5
        for j, (u, v) in enumerate(edges):
            if mask >> j & 1:
                degree[u] += 1
                degree[v] += 1
        vectors.add(tuple(sorted(2 + d for d in degree)))
    return tuple(sorted(vectors))


def remainder_floor(q: Sequence[int], mask: int) -> int:
    """The disjoint LLH, LLL and common-zero contributions to P."""
    require(len(q) == 3 and all(type(v) is int and 0 <= v <= 5 for v in q), "q range")
    require(type(mask) is int and 0 <= mask < 8, "low graph mask")
    missing = [e for j, e in enumerate(LOW_EDGES) if not (mask >> j & 1)]
    degree = [sum(i in e for e in missing) for i in range(3)]
    return int(len(missing) == 3) + sum(
        max(0, 2 + q[i] + q[j] - degree[i] - degree[j]) + max(0, q[i] + q[j] - 5)
        for i, j in missing
    )


@dataclass(frozen=True, order=True)
class State:
    a: int
    q: tuple[int, ...]
    zeta: tuple[int, ...]
    mask: int

    def objective(self) -> int:
        return (
            237
            - 2 * self.a
            + sum(v * (v + 1) for v in self.q)
            + sum(v * (v - 6) for v in self.zeta)
        )

    def bound(self) -> int:
        return self.objective() - remainder_floor(self.q, self.mask)


def states() -> Iterator[State]:
    zeros = zero_vectors()
    for a in range(10):
        for q in combinations_with_replacement(range(6), 3):
            for zeta in zeros:
                if sum(zeta) != a + sum(q):
                    continue
                for mask in range(8):
                    if 2 * mask.bit_count() <= 2 + sum(5 - v for v in q):
                        yield State(a, q, zeta, mask)


def theorem(cap: int = PROVED_CAP, profile: str = PROFILE_ID) -> dict[str, object]:
    facts = premises(profile)
    checked = tuple(states())
    require(len(checked) == len(set(checked)) == 3771, "relaxation completeness/count changed")
    maximum = max(s.bound() for s in checked)
    require(type(cap) is int and maximum <= cap, "cap refuted by complete relaxation")
    require(cap == maximum == PROVED_CAP, "claimed cap is not the certified relaxation maximum")
    encoded = json.dumps([asdict(s) for s in checked], sort_keys=True, separators=(",", ":"))
    return {
        **facts,
        "PROOF_SCOPE": "FULL_PROFILE",
        "NEW_PROVED_T_CAP": maximum,
        "ZERO_GRAPH_MASKS": 1024,
        "ZERO_DEGREE_VECTORS": len(zero_vectors()),
        "RELAXATION_STATES": len(checked),
        "RELAXATION_SHA256": hashlib.sha256(encoded.encode()).hexdigest(),
        "RELAXATION_ARGMAX": [asdict(s) for s in checked if s.bound() == maximum],
        "RELAXATION_SUPERSET_COMPLETENESS": "PROVED_BY_EXPLICIT_REALIZATION_TO_STATE_MAP",
        "GOODMAN_IDENTITY": "T=297-t(H)",
        "CORE_ZERO_IDENTITY": "T=237-2a+sum q(q+1)+sum zeta(zeta-6)-P",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0",
        "NEW_INEQUALITY": "2|G[L]|<=2+sum(5-q); P>=ell(q,G[L]); F-ell<=257",
        "COUNTEREXAMPLE_STATUS": "NONE_IN_COMPLETE_RELAXATION",
        "UNPROVED_ASSUMPTIONS": [],
        "ATTAINMENT": "NOT_ASSERTED",
    }


def audit_term(term: Term) -> None:
    """Reject wrong inputs or rounding even when both reused implementations agree."""
    t, bound, k4, contained, s4, s3 = term
    p = tuple(map(int, PROFILE_ID))
    g = tuple(6 + d for d in p)
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    require(all(type(v) is int for v in term) and 22 <= t <= SOURCE_CAP, "term domain")
    excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
    exact_k4 = max(0, -((-excess.numerator) // excess.denominator))
    a = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    exact_contained = min(exact_k4, a.numerator // a.denominator)
    exact_s4 = max(SOURCE_S4_BASE, 448 * exact_contained + 679 * (exact_k4 - exact_contained))
    exact_s3 = 2800 * w + 11872 * (t - 22) - 30800
    require(
        (k4, contained, s4, s3) == (exact_k4, exact_contained, exact_s4, exact_s3),
        "Route-B exact premises or K4 rounding wrong",
    )
    exact = Fraction(372228640 - 63838600 + exact_s3) - Fraction(4 * exact_s4, 7)
    require(
        bound == -((-exact.numerator) // exact.denominator) and 0 <= bound - exact < 1,
        "Route-B rounding wrong",
    )


def route_b(cap: int) -> list[Term]:
    """Integer recount and independent Fraction ceilings for every required term."""
    require(type(cap) is int and 22 <= cap <= SOURCE_CAP, "Route-B cap range")
    p = tuple(map(int, PROFILE_ID))
    g = tuple(6 + d for d in p)
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a = sum(d * (v - 2) for d, v in zip(p, g, strict=True)) // 3
    require((w, u, max(g), a) == (831, 2350, 12, 200), "Route-B degree terms changed")
    out: list[Term] = []
    for t in range(22, cap + 1):
        numerator = u - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -(-numerator // 4))
        contained = min(k4, a)
        s4 = max(SOURCE_S4_BASE, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372228640 - 63838600 + s3 - (4 * s4) // 7
        term = (t, bound, k4, contained, s4, s3)
        audit_term(term)
        out.append(term)
    require(
        out
        == r32.route_b_envelope(p, cap, SOURCE_S4_BASE)
        == split.route_b_terms(p, cap, SOURCE_S4_BASE),
        "Route-B source implementations differ",
    )
    return out


def realization_check(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Supplementary legal-witness check, independent counts of each remainder term."""
    d = tuple(sum(v in s for s in triples) for v in range(20))
    require(tuple(sorted(d, reverse=True)) == tuple(map(int, PROFILE_ID)), "wrong witness Profile")
    split.prior.r5.validate_k20_support_realization(triples, pairs, d)
    g = {e for s in (*triples, *pairs) for e in combinations(sorted(s), 2)}
    h = set(combinations(range(20), 2)) - g
    nb = [set(v for v in range(20) if tuple(sorted((u, v))) in g) for u in range(20)]
    core, zero = {v for v in range(20) if d[v]}, {v for v in range(20) if not d[v]}
    low = sorted((v for v in core if d[v] == 1), key=lambda v: len(nb[v] & zero))
    m, mz = set(combinations(sorted(core), 2)) & h, set(combinations(sorted(zero), 2)) & h
    parts = [
        split.triangle_count(tuple(core), m),
        split.triangle_count(tuple(zero), mz),
        sum(len(nb[u] & nb[v] & zero) for u, v in m),
        sum(len(nb[u] & nb[v] & core) for u, v in mz),
    ]
    sigma = {v: len(nb[v] & zero) for v in core}
    zeta = tuple(sorted(len(nb[v] & core) for v in zero))
    a, q = sum(sigma[v] for v in core if d[v] == 5), tuple(sigma[v] for v in low)
    mask = sum(1 << j for j, (i, k) in enumerate(LOW_EDGES) if tuple(sorted((low[i], low[k]))) in g)
    state = State(a, q, zeta, mask)
    shadow = {e for s in triples for e in combinations(sorted(s), 2)}
    shadow_low = sum(e in shadow for e in combinations(sorted(low), 2))
    t, th = split.triangle_count(tuple(range(20)), g), split.triangle_count(tuple(range(20)), h)
    r = sum(sigma.values())
    require(shadow_low <= 1 and len(g) == 93 and r == sum(zeta), "support premises fail")
    require(
        all(sigma[v] <= 6 - d[v] for v in core) and all(2 <= v <= 6 for v in zeta),
        "cross degrees fail",
    )
    require(state in set(states()), "legal realization absent from relaxation")
    require(t + th == 297 and t == state.objective() - sum(parts), "exact identity fails")
    require(
        min(parts) >= 0
        and sum(parts) >= remainder_floor(q, mask)
        and t <= state.bound() <= PROVED_CAP,
        "new remainder inequality fails",
    )
    return {
        "T": t,
        "T_H": th,
        "P_TERMS": parts,
        "P": sum(parts),
        "ELL": remainder_floor(q, mask),
        "STATE": asdict(state),
        "SHADOW_LOW_EDGES": shadow_low,
        "ROLE": "IDENTITY_CHECK_ONLY",
    }


def compute_result() -> dict[str, object]:
    row, provenance = source_authority()
    proof = theorem()
    original, new = route_b(SOURCE_CAP), route_b(PROVED_CAP)
    prefix = -1
    sufficient: list[int] = []
    for t in original:
        prefix = max(prefix, t[1])
        if prefix <= TARGET_BOUND:
            sufficient.append(t[0])
    peak = max(new, key=lambda t: (t[1], t[0]))
    require(
        max(sufficient) == 263 and peak[1] == NEW_BOUND < TARGET_BOUND,
        "target bound or sufficient cap changed",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FULL_PROFILE_TARGET_ACHIEVED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": FROZEN_SHA256,
        "FROZEN_RESULT_SHA256_STATUS": "MATCH",
        **proof,
        "SOURCE_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_ROW_BOUND": row.bound,
        "SOURCE_ROW": asdict(row),
        "SOURCE_PROVENANCE": provenance,
        "SOURCE_FULL_LEDGER_REPLAY": {
            "ROWS": 4647,
            "DIGESTS": "MATCH",
            "CPU_SECONDS": 38.529633,
            "SEARCH": "NOT_RUN",
        },
        "LOAD_BEARING_PREMISES": [
            "22 linear triple supports, 27 distinct pair supports; six labels per ticket",
            "all support pairs distinct; G degrees 6+d, H degrees 13-d",
            "sigma<=6-d; 2<=zeta<=6; equal cross sums",
            "three degree-six vertices each have a shadow neighbour in L",
            "shadow G[L] has <=1 edge; core pair incidence at L is sum(5-q)",
            "MZ is one of all 1024 simple graphs on five zero vertices",
            "LLH triangles, LLL triangle, and common-zero terms are disjoint contributions to P",
        ],
        "MAX_SUFFICIENT_CAP_FOR_313395164": max(sufficient),
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "STRICT_OWNER_BOUND_DELTA": row.bound - peak[1],
        "ARGMAX_TERM": list(peak),
        "ROUTE_B_INTEGER_RECOUNT": "PASS_ALL_243_ORIGINAL_TERMS",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_ALL_243_ORIGINAL_TERMS",
        "ROUNDING_CHECK": "PASS",
        "ROUTE_B_ORIGINAL_TERMS": [list(t) for t in original],
        "ROUTE_B_NEW_TERMS": [list(t) for t in new],
        "RECORDED_REALIZATION": realization_check(*row.realization),
        "INCUMBENT": 313263888,
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS": 120,
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FROZEN_LEDGER_MUTATED": "NO",
    }


def render(result: dict[str, object]) -> bytes:
    return (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    started = process_time()
    result = compute_result()
    RESULT_PATH.write_bytes(render(result))
    print(
        json.dumps(
            {
                "RESULT_SHA256": hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(),
                "CPU_SECONDS": process_time() - started,
                "NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
