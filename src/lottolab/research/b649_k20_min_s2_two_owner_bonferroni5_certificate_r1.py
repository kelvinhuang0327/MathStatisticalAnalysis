"""Two cap-term Bonferroni-5 certificates on the pinned complete Minimum-S2 ledger.

Official events use seven selected labels, each with seven choices of special.
Pair linearity bounds the winner multiplicity by C(7,2)/C(3,2)=7. On five
tickets at most two linear triple supports fit. With no triple, seven labels
supply at most fourteen hits. With one triple tau, the six cross-pair labels
to two common outside neighbours are the unique winning seven-set, weight 7;
the edge between the outside neighbours is irrelevant. With two triples
meeting at c, all four cross edges between their exclusive pairs are required.
The two triple labels, those four pair labels, and one of the four labels
projecting to {c} give four winning seven-sets, weight 28. This requires K5.
Each such K5 was counted twice by sum_tau C(m_tau,2), so its correction is +2.
Thus S5=7*(sum_tau C(m_tau,2)+2*N_2T). Every induced graph and linear packing
is checked against the pinned exact label-mask DP, including partial external
supports represented as singleton/pair labels.

For triple degrees d, graph degrees are g=6+d and m_tau<=4+min_{v in tau} d_v.
Let H_k count triple supports whose three degrees are >=k. Necessarily
H_k<=floor(sum_{d>=k} d/3), H_k<=22-max_{0<d<k} d, and H_k=0 if fewer than
three vertices have d>=k. The latter inequality follows because one low
vertex's distinct incident triples all lie outside H_k. Summation by degree
threshold bounds sum C(m_tau,2). Also N_2T<=sum_v C(d_v,2), since every pair
of intersecting linear triples has exactly one common vertex. These generic
inequalities give 760+2*136 and 799+2*136, hence S5<=7224 and <=7497.

Pointwise Bonferroni-5 minus the union indicator equals C(r-1,5)>=0 for
r>=1, and zero at r=0. Use the existing S4 floor, the degree-only S5 cap,
and MIN(existing fourth-order bound, S1-S2+S3-S4_floor+S5_cap). No credits
are added. Only two t=264 BOUND fields change. The complete maximum includes
all 4647 resolved rows and the inherited cursor, covering 4844 profiles.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_sts13_higher_order_slack_certificate_r1 as previous
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Row
from .b649_k20_min_s2_three_motif_complete_family_integration_r1 import Ledger

integration, chase, split, event = (
    previous.integration,
    previous.chase,
    previous.split,
    previous.event,
)
integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
motif, nb = previous.previous.motif, chase.prior.nb
type Support = tuple[int, ...]
type Pair = tuple[int, int]
TASK_ID = "B649_K20_MIN_S2_TWO_OWNER_BONFERRONI5_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-two-owner-bonferroni5-certificate-r1"
BASE_HEAD = "a47a89ecb64fd71a86698831f5c7d6ab3ac38232"
BASE_TREE = "a5dfd25ae49da33169ad292823ca87996f3ecf93"
BASE_RESULT_SHA256 = "d3566845db884b729a6b23ce2532c5e233e8e985c06c2b29d7b9ca699073e8a8"
# NB indices are deterministic replay locators; they are not a stored JSON array.
# The cap 264 in each originates in the pinned R30 t=265 refutation.
OWNER_SOURCES = {
    "66555555555540000000": (1442, 3291),
    "66655555555521000000": (1198, 3090),
}
CAP = 264
RESULT_FILENAME = "b649-k20-min-s2-two-owner-bonferroni5-certificate-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: Ledger
    sealed: dict[str, object]
    r30: dict[str, object]
    provenance: dict[str, str]


@cache
def load_authority() -> Authority:
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    sealed = integration.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    path = Path(previous.__file__ or "").resolve()
    relative = path.relative_to(chase.ROOT).as_posix()
    blob = chase.git("show", f"{BASE_HEAD}:{relative}")
    if path.read_bytes() != blob or hashlib.sha256(blob).hexdigest() != sealed["SOURCE_SHA256"]:
        raise AssertionError("predecessor source identity mismatch")
    inherited = previous.load_authority()
    if digest(previous.compute_result(inherited)) != digest(sealed):
        raise AssertionError("sealed predecessor replay differs")
    ledger = integration.install(
        inherited.ledger,
        previous.PROFILE,
        integer(object_row(sealed["OWNER_CERTIFICATE"])["CERTIFIED_PROFILE_BOUND"]),
        f"{previous.RESULT_FILENAME}:OWNER_CERTIFICATE",
    )
    family = integration.family(ledger, inherited.inherited.inherited.inherited)
    if family != sealed["FINAL_FAMILY"]:
        raise AssertionError("sealed complete family differs")
    r30 = integration.pinned(
        BASE_HEAD, integration.r32.CAP_SOURCE_RESULT, integration.r32.R30_SHA256
    )
    return Authority(
        inherited,
        ledger,
        sealed,
        r30,
        {**inherited.provenance, relative: hashlib.sha256(blob).hexdigest()},
    )


def s5_counts(
    vertices: Sequence[int], edges: set[Pair], triples: Sequence[Support]
) -> tuple[tuple[int, ...], int]:
    """Exact m_tau and N_2T, with no assumption about the edge outside tau."""
    common = tuple(
        sum(all(tuple(sorted((u, v))) in edges for u in tau) for v in vertices if v not in tau)
        for tau in triples
    )
    two = {
        tuple(sorted(q))
        for a, b in combinations(triples, 2)
        if len(q := set(a) | set(b)) == 5 and set(combinations(sorted(q), 2)) <= edges
    }
    return common, len(two)


def s5_identity_value(common: Sequence[int], n2: int) -> int:
    return 7 * (sum(comb(m, 2) for m in common) + 2 * n2)


@cache
def local_weight_table() -> tuple[tuple[int, ...], ...]:
    """All 2544 admissible five-ticket graph/packing cases, not a profile census."""
    pairs = tuple(combinations(range(5), 2))
    table: list[tuple[int, ...]] = []
    for packing in previous.linear_packings(5):
        shadow = {e for t in packing for e in combinations(t, 2)}
        free = tuple(e for e in pairs if e not in shadow)
        for bits in range(1 << len(free)):
            edges = shadow | {e for i, e in enumerate(free) if bits >> i & 1}
            profile = previous.local_profile(5, edges, packing)
            exact = previous.intersection_count(profile)
            common, n2 = s5_counts(tuple(range(5)), edges, packing)
            if exact != s5_identity_value(common, n2):
                raise AssertionError("five-ticket label-support identity failed")
            edge_mask = sum(1 << i for i, e in enumerate(pairs) if e in edges)
            triple_mask = sum(
                1 << i for i, t in enumerate(combinations(range(5), 3)) if t in packing
            )
            table.append(
                (edge_mask, triple_mask, len(packing), sum(comb(m, 2) for m in common), n2, exact)
            )
    if len(table) != 2544 or len({t[:2] for t in table}) != len(table):
        raise AssertionError("five-ticket local coverage differs")
    return tuple(table)


def universal_proof() -> dict[str, object]:
    table = local_weight_table()
    return {
        "STATUS": "PASS",
        "IDENTITY": "S5 = 7 * (sum_tau C(m_tau,2) + 2*N_2T)",
        "M_TAU_DEFINITION": "common outside neighbours of the three vertices of tau",
        "N_2T_DEFINITION": "five-sets containing two intersecting triple supports and forming K5",
        "EVENT_MODEL": "at least 3 hits among 7 labels; 7 special choices per selected set",
        "LOCAL_CASE_COUNT": len(table),
        "LOCAL_CASE_COUNTS_0_1_2_TRIPLES": [sum(t[2] == k for t in table) for k in range(3)],
        "LOCAL_TABLE_COLUMNS": [
            "EDGE_MASK",
            "TRIPLE_MASK",
            "TRIPLES",
            "COMMON_PAIR_SUM",
            "N_2T",
            "EXACT_OFFICIAL_WEIGHT",
        ],
        "LOCAL_WEIGHT_HISTOGRAM": [
            [k, weight, sum(t[2] == k and t[5] == weight for t in table)]
            for k in range(3)
            for weight in sorted({t[5] for t in table if t[2] == k})
        ],
        "LOCAL_WEIGHT_TABLE_SHA256": digest(table),
        "TWO_TRIPLE_K5_WEIGHT": 28,
    }


def degree_s5_cap(profile: str | Sequence[int]) -> dict[str, object]:
    d = split.profile_values(profile)
    g = tuple(6 + v for v in d)
    thresholds: list[list[int]] = []
    weights = [comb(4 + k, 2) for k in range(1, 7)]
    for k in range(1, 7):
        high = [v for v in d if v >= k]
        low = [v for v in d if 0 < v < k]
        incidence = sum(high) // 3 if len(high) >= 3 else 0
        low_vertex = 22 - max(low, default=0)
        thresholds.append(
            [k, len(high), sum(high), incidence, low_vertex, min(incidence, low_vertex)]
        )
    common_cap = 22 * weights[0] + sum(
        thresholds[k - 1][5] * (weights[k - 1] - weights[k - 2]) for k in range(2, 7)
    )
    n2_cap = sum(comb(v, 2) for v in d)
    return {
        "STATUS": "PASS",
        "D": list(d),
        "G": list(g),
        "M_TAU_CAP": "4 + min(d_v for v in tau)",
        "H_K_DEFINITION": "number of triple supports all of whose vertex degrees are >= k",
        "THRESHOLD_COLUMNS": [
            "K",
            "HIGH_VERTEX_COUNT",
            "HIGH_INCIDENCES",
            "INCIDENCE_CAP",
            "LOW_VERTEX_CAP",
            "H_K_CAP",
        ],
        "THRESHOLD_CAPS": thresholds,
        "COMMON_PAIR_SUM_CAP": common_cap,
        "N_2T_CAP": n2_cap,
        "S5_CAP": 7 * (common_cap + 2 * n2_cap),
    }


def bonferroni_check() -> dict[str, object]:
    table: list[list[int]] = []
    for r in range(8):
        partial = sum((-1) ** (k + 1) * comb(r, k) for k in range(1, 6))
        excess = partial - int(r > 0)
        expected = comb(r - 1, 5) if r else 0
        if excess != expected or excess < 0:
            raise AssertionError("unsafe fifth-order Bonferroni inequality")
        table.append([r, partial, int(r > 0), excess])
    return {"STATUS": "PASS", "R_CAP": 7, "TABLE": table, "INEQUALITY": "Union <= S1-S2+S3-S4+S5"}


def check_cap(pid: str, row: Row, proof: Mapping[str, object]) -> None:
    index, attempt = OWNER_SOURCES[pid]
    d = split.profile_values(pid)
    w = sum(comb(6 + v, 2) for v in d)
    expected: dict[str, object] = {
        "ATTEMPT_INDEX": attempt,
        "PROFILE_IDS": [pid],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "ROUTE": integration.r32.CAP_SOURCE_ROUTE,
        "WEDGE_COUNT": w,
        "TARGET_TRIANGLE_CAP": CAP,
        "REFUTED_GRAPH_TRIANGLE_COUNT": CAP + 1,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": CAP,
        "OPEN_WEDGE_CEILING_REFUTED": w - 3 * (CAP + 1),
        "CERTIFIED_OPEN_WEDGE_LOWER_BOUND": w - 3 * (CAP + 1) + 1,
    }
    if (
        type(row.cap) is not int
        or row.cap != CAP
        or row.source != f"{nb.RESULT_FILENAME}:NB_CERTIFICATES[{index}]"
        or row.s4_base != nb.r28.profile_s4_floor(d)
        or any(digest(proof.get(k)) != digest(v) for k, v in expected.items())
        or integration.r32.r28.r26.accepted_cap(proof, (d,), CAP) != CAP
        or nb.combined_triangle_cap(nb.profile_nb_cap(d)[2], nb.r18_cap(d), CAP) != CAP
    ):
        raise AssertionError("owner cap-source identity mismatch")


def moment_bounds(s3: int, s4: int, s5: int) -> tuple[int, int]:
    """Ceil the rational fourth-order bound; the fifth-order bound is integral."""
    exact = event.K20_S1 - event.K20_S2 + s3 - Fraction(4 * s4, 7)
    fourth = -(-exact.numerator // exact.denominator)
    fifth = event.K20_S1 - event.K20_S2 + s3 - s4 + s5
    return fourth, fifth


def owner_certificate(pid: str, row: Row, proof: Mapping[str, object]) -> dict[str, object]:
    check_cap(pid, row, proof)
    d = split.profile_values(pid)
    old = split.route_b_terms(d, row.cap, row.s4_base)
    previous.previous.exact_terms(d, old, row.cap)
    *lower, last = old
    t, old_bound, _k, _a, s4, s3 = last
    if t != CAP or old_bound != row.bound or max(term[1] for term in old) != row.bound:
        raise AssertionError("load-bearing envelope differs from sealed ledger")
    cap = degree_s5_cap(d)
    fourth, fifth = moment_bounds(s3, s4, integer(cap["S5_CAP"]))
    if old_bound != fourth:
        raise AssertionError("fourth-order rounding changed")
    new_bound = min(old_bound, fifth)
    terms = [*lower, (t, new_bound, *last[2:])]
    return {
        "STATUS": "PASS",
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": CAP,
        "LOAD_BEARING_T": t,
        "CAP_SOURCE": row.source,
        "ORIGINAL_CAP_SOURCE": f"{integration.r32.CAP_SOURCE_RESULT}:GROUP_ATTEMPTS"
        f"[{OWNER_SOURCES[pid][1]}]",
        "CAP_SOURCE_IDENTITY": dict(proof),
        "DEGREE_S5_PROOF": cap,
        "S4_BASE": row.s4_base,
        "EXISTING_S4_FLOOR": s4,
        "OLD_T264_BOUND": old_bound,
        "BONFERRONI5_T264_BOUND": fifth,
        "NEW_T264_BOUND": new_bound,
        "EXACT_INTEGER_GAIN": old_bound - new_bound,
        "BOUND_RULE": "MIN(EXISTING_FOURTH_ORDER, BONFERRONI5); NEVER ADD CREDITS",
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(term[1] for term in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "ALL_T_TERMS": [list(term) for term in terms],
        "CERTIFIED_PROFILE_BOUND": max(term[1] for term in terms),
    }


def verify_certificate(
    cert: Mapping[str, object], pid: str, row: Row, proof: Mapping[str, object]
) -> None:
    if digest(cert) != digest(owner_certificate(pid, row, proof)):
        raise AssertionError("tampered Bonferroni5 certificate")


def witness_soundness(ledger: Mapping[str, Row], certs: Mapping[str, object]) -> dict[str, object]:
    named = {pid: ledger[pid].realization for pid in OWNER_SOURCES}
    named.update({kind: split.witness_supports(kind) for kind in ("P2", "STS13")})
    checks: dict[str, object] = {}
    for name, supports in named.items():
        if supports is None:
            raise AssertionError("applicable owner witness missing")
        triples, pairs = supports
        seen = motif.realization_check(triples, pairs)
        pid = integration.text(seen["PROFILE_ID"])
        d = tuple(sum(v in tau for tau in triples) for v in range(20))
        edges = {e for tau in triples for e in combinations(tau, 2)} | {(a, b) for a, b in pairs}
        common, n2 = s5_counts(tuple(range(20)), edges, triples)
        s5 = s5_identity_value(common, n2)
        direct = 0
        for q in combinations(range(20), 5):
            local = [tau for tau in triples if set(tau) <= set(q)]
            ms, two = s5_counts(q, edges, local)
            direct += s5_identity_value(ms, two)
        cap = degree_s5_cap(d)
        t, s4 = integer(seen["TRIANGLES"]), integer(seen["EXACT_S4_FROM_PINNED_LOCAL_TABLE"])
        if direct != s5 or s5 > integer(cap["S5_CAP"]):
            raise AssertionError("degree cap excludes legal witness S5")
        s3, _ = chase.r20.bound_from_cap(split.profile_values(d), t, s4)
        fifth = event.K20_S1 - event.K20_S2 + s3 - s4 + s5
        if pid in certs:
            cert = object_row(certs[pid])
            if (
                t > ledger[pid].cap
                or (t == CAP and s4 < integer(cert["EXISTING_S4_FLOOR"]))
                or fifth > integer(cert["NEW_T264_BOUND"])
            ):
                raise AssertionError("new bound excludes legal owner witness")
        checks[name] = {
            **seen,
            "EXACT_S5": s5,
            "S5_CAP": cap["S5_CAP"],
            "M_TAU": list(common),
            "N_2T": n2,
            "EXACT_BONFERRONI5_UPPER_BOUND": fifth,
            "SUPPORTS_SHA256": digest(supports),
        }
    sts = previous.higher_order_sums(*split.witness_supports("STS13"))
    if object_row(checks["STS13"])["EXACT_S5"] != sts["S5"]:
        raise AssertionError("STS13 exact S5 differs from inherited witness")
    previous.witness_soundness(ledger[previous.PROFILE].bound, previous.load_authority())
    return {"STATUS": "PASS", "WITNESSES": checks, "STS13_EXACT_UNION": sts}


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    certs: dict[str, object] = {}
    final = dict(auth.ledger)
    for pid, (_index, attempt) in OWNER_SOURCES.items():
        proof = object_row(rows(auth.r30["GROUP_ATTEMPTS"])[attempt])
        cert = owner_certificate(pid, auth.ledger[pid], proof)
        verify_certificate(cert, pid, auth.ledger[pid], proof)
        certs[pid] = cert
        final = integration.install(
            final,
            pid,
            integer(cert["CERTIFIED_PROFILE_BOUND"]),
            f"{RESULT_FILENAME}:OWNER_CERTIFICATES[{pid}]",
        )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != set(OWNER_SOURCES):
        raise AssertionError("only the two targeted rows may change")
    family_auth = auth.inherited.inherited.inherited.inherited
    start = integration.family(auth.ledger, family_auth)
    family = integration.family(final, family_auth)
    if (start["CURSOR_ID"], start["CURSOR_BOUND"], start["COVERAGE"]) != (
        family["CURSOR_ID"],
        family["CURSOR_BOUND"],
        family["COVERAGE"],
    ):
        raise AssertionError("cursor authority or coverage changed")
    soundness = witness_soundness(final, certs)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "MODULE_PROVENANCE": auth.provenance,
        "PROOF": __doc__,
        "S5_IDENTITY": universal_proof(),
        "S5_IDENTITY_STATUS": "PASS",
        "BONFERRONI5": bonferroni_check(),
        "OWNER_CERTIFICATES": certs,
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - 2,
        "OTHER_ROWS_SHA256": digest(
            {pid: r.bound for pid, r in final.items() if pid not in OWNER_SOURCES}
        ),
        "INHERITED_CERTIFICATES": auth.sealed["INHERITED_CERTIFICATES"],
        "STS13_CERTIFICATE_SHA256": digest(auth.sealed["OWNER_CERTIFICATE"]),
        "STS13_ROW_UNCHANGED": final[previous.PROFILE] == auth.ledger[previous.PROFILE],
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "DOUBLE_COUNT_STATUS": "PASS_MIN_OF_BOUNDS_NO_ADDITIVE_CREDITS",
        "WITNESS_SOUNDNESS": soundness,
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        "CURSOR_AUTHORITY_STATUS": "UNCHANGED",
        "HISTORICAL_RESULT_BYTES_PRESERVED": True,
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PROFILE_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def verify_result(result: Mapping[str, object], authority: Authority | None = None) -> None:
    if digest(result) != digest(compute_result(authority)):
        raise AssertionError("tampered immutable Bonferroni5 result")


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable Bonferroni5 result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(integration.render(result))
    print(json.dumps({k: result[k] for k in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")}))


if __name__ == "__main__":
    main()
