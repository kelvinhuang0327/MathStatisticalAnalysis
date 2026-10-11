"""One owner's t=264 quartet-incidence certificate, from the immutable 2f709256 ledger.

K/D/P/C count induced K4/diamond/paw/claw quartets. A/D1/P1 count those
K4/diamond/paw quartets containing a triple-label support. Pair linearity
allows at most one such support per quartet. J counts a vertex and three
neighbours; R counts a centred open wedge and another neighbour; B counts a
triple support and an edge from it to an outside vertex. Double counting gives
J=4K+2D+P+C, R=2D+2P+3C, B=3A+2D1+P1. The pinned local event DP gives
S4=679K-231A+112(D-D1). Eliminating D and A yields the exact identity
S4=231K+112J-56R-77B+56C+42D1+77P1. The last three terms are nonnegative.

R=sum_v OW(v)(g_v-2)<=OW*(max(g)-2); 4K=J-R+P+2C>=J-R.
At this owner's t=264: R<=410, K>=ceil(1950/4)=488, S4>=307580.
Only that term changes. All lower-t terms and every other ledger row survive.
No new solver, census, portfolio search or official-outcome enumeration runs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_higher_order_closure_r2 as event
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as base

split = base.split
prior = base.prior
r32 = prior.r32
TASK_ID = "B649_K20_MIN_S2_OWNER_66655555555440000000_MOTIF_R1"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
BASE_RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
PROFILE_ID = "66655555555440000000"
PROFILE = split.profile_values(PROFILE_ID)
CAP = 264
CAP_INDEX = 2981
RESULT_FILENAME = "b649-k20-min-s2-owner-66655555555440000000-motif-r1-result.json"
RESULT_PATH = base.ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
WEIGHTS = {"K": 679, "A": 448, "D": 112, "ZERO": 0}
HISTORICAL_SOURCE_NAMES = (
    "b649_k20_min_s2_class_dominance_or_descent_r13",
    "b649_k20_min_s2_closed_form_owner_plateau_r31",
    "b649_k20_min_s2_continued_multi_plateau_descent_r12",
    "b649_k20_min_s2_current_bound_owner_refinement_r15",
    "b649_k20_min_s2_current_cursor_class_owner_chase_r28",
    "b649_k20_min_s2_current_cursor_dynamic_family_max_r30",
    "b649_k20_min_s2_cursor_plateau_closure_r18",
    "b649_k20_min_s2_dangerous_core_realizability_r5",
    "b649_k20_min_s2_higher_order_closure_r2",
    "b649_k20_min_s2_load_bearing_plateau_descent_r16",
    "b649_k20_min_s2_nb_degree_cap_frontier_r1",
    "b649_k20_min_s2_nb_w807_w786_batch_certificate_r1",
    "b649_k20_min_s2_nb_w808_frontier_r1",
    "b649_k20_min_s2_next_active_profile_exact_bound_r8",
    "b649_k20_min_s2_next_distinct_plateau_r10",
    "b649_k20_min_s2_r16_freeze_and_owner_refinement_r17",
    "b649_k20_min_s2_realizable_core_class_bound_r4",
    "b649_k20_min_s2_resolved_above_cursor_owner_chase_r20",
    "b649_k20_min_s2_route_b_current_owner_refinement_r32",
    "b649_k20_min_s2_six_owner_batch_refinement_r26",
    "b649_k20_min_s2_six_owner_cursor_crossover_r26",
    "b649_k20_min_s2_split_cap_current_owner_chase_r1",
    "b649_k20_min_s2_ss332_owner_class_to_cursor_r29",
    "b649_k20_min_s2_successive_class_dominance_r14",
    "b649_k20_min_s2_topw12_coverage_repair_r1",
    "b649_k20_min_s2_topw12_split_cap_certificate_r1",
    "b649_official_any_prize_exact",
)
Pair = tuple[int, int]
Support = tuple[int, ...]
integer, object_row, rows = base.integer, base.object_row, base.rows


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def pinned_result(filename: str, expected: str | None = None) -> dict[str, object]:
    blob = base.git("show", f"{BASE_HEAD}:{prior.RESULT_DIRECTORY}/{filename}")
    if expected is not None and hashlib.sha256(blob).hexdigest() != expected:
        raise AssertionError("pinned result digest mismatch")
    return object_row(json.loads(blob))


@dataclass(frozen=True)
class Motifs:
    k: int = 0
    d: int = 0
    p: int = 0
    c: int = 0
    a: int = 0
    d1: int = 0
    p1: int = 0

    @property
    def j(self) -> int:
        return 4 * self.k + 2 * self.d + self.p + self.c

    @property
    def r(self) -> int:
        return 2 * self.d + 2 * self.p + 3 * self.c

    @property
    def b(self) -> int:
        return 3 * self.a + 2 * self.d1 + self.p1

    @property
    def s4(self) -> int:
        return WEIGHTS["K"] * self.k - 231 * self.a + WEIGHTS["D"] * (self.d - self.d1)

    @property
    def dropped(self) -> int:
        return 56 * self.c + 42 * self.d1 + 77 * self.p1


def classify(edges: set[Pair], triple: Support | None) -> Motifs:
    """Classify one induced four-vertex graph; labels outside it are irrelevant."""
    degrees = [sum(v in e for e in edges) for v in range(4)]
    k = int(len(edges) == 6)
    d = int(len(edges) == 5)
    p = int(len(edges) == 4 and max(degrees) == 3)
    c = int(len(edges) == 3 and max(degrees) == 3)
    supported = int(triple is not None)
    return Motifs(k, d, p, c, k * supported, d * supported, p * supported)


def incidences(n: int, edges: set[Pair], triples: Sequence[Support]) -> tuple[int, int, int]:
    """Count the three incidence sets directly, without motif identities."""
    neighbours = [{w for w in range(n) if tuple(sorted((v, w))) in edges} for v in range(n)]
    j = sum(comb(len(adj), 3) for adj in neighbours)
    r = sum(
        (len(adj) - 2) * sum((a, b) not in edges for a, b in combinations(sorted(adj), 2))
        for adj in neighbours
    )
    b = sum(len(neighbours[v] - set(t)) for t in triples for v in t)
    return j, r, b


def local_weight(edges: set[Pair], triple: Support | None) -> int:
    """Pinned OFFICIAL_ANY_PRIZE event DP, on a local incidence mask only."""
    counts = [0] * 16
    support_edges: set[Pair] = set(combinations(triple, 2)) if triple is not None else set()
    if not support_edges <= edges:
        raise ValueError("a triple support must induce a triangle")
    if triple is not None:
        counts[sum(1 << v for v in triple)] = 1
    for a, b in edges - support_edges:
        counts[(1 << a) | (1 << b)] = 1
    for v in range(4):
        counts[1 << v] = 6 - sum(count for mask, count in enumerate(counts) if mask >> v & 1)
    counts[0] = event.BIG_LOTTO_POOL_SIZE - sum(counts)
    return event.compressed_four_ticket_intersection_count(
        counts,
        pool_size=event.BIG_LOTTO_POOL_SIZE,
        draw_size=event.BIG_LOTTO_DRAW_SIZE,
        outright_matches=event.BIG_LOTTO_OUTRIGHT_MATCHES,
    )


@cache
def local_identity_check() -> dict[str, object]:
    """All 64 local graphs and all legal zero/one contained-support choices."""
    pairs = tuple(combinations(range(4), 2))
    table: list[list[int]] = []
    for mask in range(64):
        edges = {e for i, e in enumerate(pairs) if mask >> i & 1}
        supports: list[Support | None] = [
            None,
            *(t for t in combinations(range(4), 3) if set(combinations(t, 2)) <= edges),
        ]
        for triple in supports:
            m = classify(edges, triple)
            j, r, b = incidences(4, edges, () if triple is None else (triple,))
            if (j, r, b) != (m.j, m.r, m.b):
                raise AssertionError("quartet incidence identity failed")
            weight = local_weight(edges, triple)
            if weight != m.s4:
                raise AssertionError("quartet weight identity failed")
            if 4 * m.k != j - r + m.p + 2 * m.c:
                raise AssertionError("K4 elimination identity failed")
            if m.s4 != 231 * m.k + 112 * j - 56 * r - 77 * b + m.dropped:
                raise AssertionError("nonnegative elimination identity failed")
            if m.dropped < 0 or not (m.a <= m.k and m.d1 <= m.d and m.p1 <= m.p):
                raise AssertionError("dropped terms must be nonnegative motif counts")
            table.append(
                [mask, 0 if triple is None else sum(1 << v for v in triple), j, r, b, weight]
            )
    if len(table) != 96 or {row[-1] for row in table} != set(WEIGHTS.values()):
        raise AssertionError("local graph/support coverage changed")
    return {
        "STATUS": "PASS",
        "LOCAL_CASES": len(table),
        "TABLE_SHA256": digest(table),
        "WEIGHTS": WEIGHTS,
        "TABLE_COLUMNS": ["EDGES_MASK", "TRIPLE_MASK", "J", "R", "B", "S4"],
        "TABLE": table,
        "DROPPED_TERMS": "56C+42D1+77P1 >= 0",
    }


def degree_floor(profile: Sequence[int], triangles: int) -> dict[str, int]:
    g = [6 + d for d in profile]
    w = sum(comb(v, 2) for v in g)
    j = sum(comb(v, 3) for v in g)
    b = sum(d * (v - 2) for d, v in zip(profile, g, strict=True))
    ow = w - 3 * triangles
    if ow < 0:
        raise ValueError("negative open-wedge count")
    r_max = (max(g) - 2) * ow
    k = max(0, -(-(j - r_max) // 4))
    constant = 112 * j - 56 * r_max - 77 * b
    s4 = max(0, 231 * k + constant)
    if k and not Fraction(k - 1) < Fraction(j - r_max, 4) <= k:
        raise AssertionError("K4 ceiling is not exact")
    return {
        "W": w,
        "J": j,
        "B": b,
        "OW": ow,
        "R_MAX": r_max,
        "K4_BOUND": k,
        "S4_CONSTANT": constant,
        "S4_CERTIFIED_FLOOR": s4,
    }


def check_cap(proof: Mapping[str, object], row: base.Row) -> None:
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": CAP_INDEX,
        "PROFILE_IDS": [PROFILE_ID],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": r32.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": 833,
        "TARGET_TRIANGLE_CAP": CAP,
        "REFUTED_GRAPH_TRIANGLE_COUNT": CAP + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": CAP,
        "OPEN_WEDGE_CEILING_REFUTED": 38,
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": 39,
    }
    if (
        type(row.cap) is not int
        or row.cap != CAP
        or any(digest(proof.get(k)) != digest(v) for k, v in expected.items())
    ):
        raise AssertionError("cap-source identity mismatch")
    if r32.r28.r26.accepted_cap(proof, (PROFILE,), CAP) != CAP:
        raise AssertionError("cap-source refutation not accepted")


def owner_certificate(row: base.Row, proof: Mapping[str, object]) -> dict[str, object]:
    check_cap(proof, row)
    old = split.route_b_terms(PROFILE, row.cap, row.s4_base)
    floor = degree_floor(PROFILE, CAP)
    s4 = max(row.s4_base, floor["S4_CERTIFIED_FLOOR"])
    s3, bound = base.r20.bound_from_cap(PROFILE, CAP, s4)
    credit = 4 * s4 // 7
    exact = event.K20_S1 - event.K20_S2 + s3 - Fraction(4 * s4, 7)
    if not 0 <= bound - exact < 1 or bound != event.K20_S1 - event.K20_S2 + s3 - credit:
        raise AssertionError("S4 credit rounding is not exact")
    new = [*old[:-1], (CAP, bound, floor["K4_BOUND"], None, s4, s3)]
    if old[-1][0] != CAP or max(t[1] for t in old) != row.bound:
        raise AssertionError("existing owner envelope does not reproduce the base ledger")
    return {
        "PROFILE_ID": PROFILE_ID,
        "TRIANGLE_CAP": CAP,
        "TRIANGLE_CAP_AUTHORITY": f"R30 GROUP_ATTEMPTS[{CAP_INDEX}], t=265 INFEASIBLE",
        "CAP_SOURCE": f"{r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS[{CAP_INDEX}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "EXISTING_LEDGER_SOURCE": row.source,
        "D": list(PROFILE),
        "G": [6 + d for d in PROFILE],
        **floor,
        "T264_OLD_BOUND": old[-1][1],
        "OLD_ROUTE_B_S4_FLOOR": old[-1][4],
        "OLD_ROUTE_B_CREDIT": 4 * old[-1][4] // 7,
        "NEW_ROUTE_B_CREDIT": credit,
        "EXTRA_CREDIT": credit - 4 * old[-1][4] // 7,
        "T264_NEW_BOUND": bound,
        "T263_RETAINED_MAX": max(t[1] for t in old[:-1]),
        "CERTIFIED_OWNER_BOUND": max(t[1] for t in new),
        "RETAINED_TERMS_SHA256": digest(old[:-1]),
        "ALL_T_TERMS": [list(t) for t in new],
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "ROUTE_B_CONTAINED_K4_CAP", "S4", "S3"],
        "T264_CONTAINED_K4_CAP": "NOT_USED_BY_INCIDENCE_INEQUALITY",
        "ROUNDING": "CEIL((J-R_MAX)/4); FLOOR(4*S4/7)",
        "STATUS": "PASS",
    }


def verify_certificate(
    cert: Mapping[str, object], row: base.Row, proof: Mapping[str, object]
) -> None:
    if digest(cert) != digest(owner_certificate(row, proof)):
        raise AssertionError("tampered owner certificate")


@dataclass(frozen=True)
class Authority:
    ledger: dict[str, base.Row]
    coverage: dict[str, object]
    proof: dict[str, object]
    provenance: dict[str, str]


def historical_provenance() -> dict[str, str]:
    """Verify exactly the 27 historical sources used by this certificate's replay."""
    provenance: dict[str, str] = {}
    for name in HISTORICAL_SOURCE_NAMES:
        module = sys.modules.get(f"{__package__}.{name}")
        if module is None or module.__file__ is None:
            raise AssertionError(f"historical source module missing: {name}")
        relative = f"src/lottolab/research/{name}.py"
        path = Path(module.__file__).resolve()
        if path != (base.ROOT / relative).resolve():
            raise AssertionError(f"historical source identity mismatch: {name}")
        committed = base.git("show", f"{BASE_HEAD}:{relative}")
        if path.read_bytes() != committed:
            raise AssertionError(f"reused module differs from base: {relative}")
        provenance[relative] = hashlib.sha256(committed).hexdigest()
    return provenance


@cache
def load_authority() -> Authority:
    """Replay the existing ledger, then install only the base's sealed split-cap rows."""
    if base.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    sealed = pinned_result(base.RESULT_FILENAME, BASE_RESULT_SHA256)
    provenance = historical_provenance()
    inherited = base.load_authority()
    ledger = dict(inherited.ledger)
    for index, raw in enumerate(rows(sealed["CERTIFICATES"])):
        cert = object_row(raw)
        pid = base.text(cert["PROFILE_ID"])
        if base.refine(pid, ledger[pid]) != cert:
            raise AssertionError("sealed base certificate replay diverged")
        if cert["STATUS"] == base.TIGHTENED:
            ledger[pid] = replace(
                ledger[pid],
                bound=integer(cert["ALL_T_MAX_BOUND"]),
                cap=integer(cert["TRIANGLE_CAP"]),
                source=f"{base.RESULT_FILENAME}:CERTIFICATES[{index}]",
            )
    summary = base.final_family(ledger, base.Outcome(ledger, [], [], object_row(sealed["STOP"])))
    if (
        any(sealed.get(k) != v for k, v in summary.items())
        or sealed["COVERAGE"] != inherited.coverage
    ):
        raise AssertionError("actual base ledger or coverage does not reproduce sealed result")
    r30 = pinned_result(r32.CAP_SOURCE_RESULT, r32.R30_SHA256)
    proof = object_row(rows(r30["GROUP_ATTEMPTS"])[CAP_INDEX])
    check_cap(proof, ledger[PROFILE_ID])
    return Authority(ledger, inherited.coverage, proof, provenance)


def realization_check(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Legal support validation and direct graph incidence counts, without outcome enumeration."""
    profile = tuple(sum(v in t for t in triples) for v in range(20))
    prior.r5.validate_k20_support_realization(triples, pairs, profile)
    edges = split.edges_of((*triples, *pairs))
    totals = [0] * 7
    for q in combinations(range(20), 4):
        local_edges = {(q.index(a), q.index(b)) for a, b in edges if a in q and b in q}
        supports = [t for t in triples if set(t) <= set(q)]
        if len(supports) > 1:
            raise AssertionError("pair linearity forbids two contained triple supports")
        support = tuple(q.index(v) for v in supports[0]) if supports else None
        m = classify(local_edges, support)
        for i, value in enumerate((m.k, m.d, m.p, m.c, m.a, m.d1, m.p1)):
            totals[i] += value
    motifs = Motifs(*totals)
    j, r, b = incidences(20, edges, triples)
    t = split.triangle_count(tuple(range(20)), edges)
    floor = degree_floor(profile, t)
    if (j, r, b) != (motifs.j, motifs.r, motifs.b):
        raise AssertionError("realization incidence identities failed")
    if motifs.s4 != 231 * motifs.k + 112 * j - 56 * r - 77 * b + motifs.dropped:
        raise AssertionError("realization elimination identity failed")
    if (
        r > floor["R_MAX"]
        or motifs.k < floor["K4_BOUND"]
        or motifs.s4 < floor["S4_CERTIFIED_FLOOR"]
    ):
        raise AssertionError("incidence bound excludes a legal realization")
    return {
        "STATUS": "PASS",
        "PROFILE_ID": base.r20.profile_id(tuple(sorted(profile, reverse=True))),
        "TRIANGLES": t,
        "MOTIFS_K_D_P_C_A_D1_P1": totals,
        "J": j,
        "R": r,
        "B": b,
        "EXACT_S4_FROM_PINNED_LOCAL_TABLE": motifs.s4,
        "DEGREE_FLOOR": floor,
    }


def compute_result() -> dict[str, object]:
    auth = load_authority()
    local = local_identity_check()
    cert = owner_certificate(auth.ledger[PROFILE_ID], auth.proof)
    verify_certificate(cert, auth.ledger[PROFILE_ID], auth.proof)
    ledger = dict(auth.ledger)
    ledger[PROFILE_ID] = replace(
        ledger[PROFILE_ID],
        bound=integer(cert["CERTIFIED_OWNER_BOUND"]),
        source=f"{RESULT_FILENAME}:OWNER_CERTIFICATE",
    )
    if {p for p in ledger if ledger[p] != auth.ledger[p]} != {PROFILE_ID}:
        raise AssertionError("only this owner may change")
    family, owners = base.family_state(ledger)
    recompute = base.final_family(
        ledger, base.Outcome(ledger, [], [], {"FAMILY": family, "OWNER_IDS": owners})
    )
    witness = auth.ledger[PROFILE_ID].realization
    if witness is None:
        raise AssertionError("target owner's committed legal realization missing")
    checks = {
        "OWNER": realization_check(*witness),
        **{kind: realization_check(*split.witness_supports(kind)) for kind in ("P2", "STS13")},
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "MODULE_PROVENANCE": auth.provenance,
        "PROOF": __doc__,
        "OWNER_CERTIFICATE": cert,
        "INCIDENCE_IDENTITIES": local,
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        "LEGAL_REALIZATIONS": checks,
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "COVERAGE": auth.coverage,
        "OTHER_COMMITTED_PROFILE_ROWS_UNCHANGED": len(ledger) - 1,
        "OTHER_ROWS_SHA256": digest({p: r.bound for p, r in ledger.items() if p != PROFILE_ID}),
        "COMPLETE_FAMILY_BOUND_FROM_BASE": family,
        "FAMILY_RECOMPUTATION": recompute,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "FULL_CENSUS_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
    }


def verify_result(result: Mapping[str, object]) -> None:
    if digest(result) != digest(compute_result()):
        raise AssertionError("tampered immutable result")


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    cert = object_row(result["OWNER_CERTIFICATE"])
    print(json.dumps({k: cert[k] for k in ("T264_NEW_BOUND", "CERTIFIED_OWNER_BOUND")}))


if __name__ == "__main__":
    main()
