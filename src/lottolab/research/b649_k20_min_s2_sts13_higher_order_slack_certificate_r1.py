"""Universal higher-order slack for the pinned STS13 t=270 term.

Write Si=sum_{|Q|=i}|intersection_{j in Q} E_j|=sum_outcomes C(r,i).
The pinned event is three hits in the seven selected labels (six main plus
special), with seven choices of special per selected set. Pair linearity
implies r<=7: the three chosen hit labels of each winner use three distinct
pairs among the seven labels. Integer replay below proves
  7 Delta = 3 S4 - 7 S5 + 7 S6 - 7 S7,
where Delta is the excess of S1-S2+S3-(4/7)S4 over the exact union.

Use the inherited isolation K12 + (K8-e), without reimplementing its proof.
Every label support lies in one component. K12 has twenty linear triples,
each vertex in five; K8-e has two disjoint triples on its six degree-7 vertices.
A local profile is uniquely determined by its induced edges and contained
triples: uncovered edges are pair labels, residual capacity is singleton
labels, and all other labels have mask zero. Partial external triples are
therefore included, rather than discarded. The finite local DP counts labels,
not all official outcomes or STS presentations.

On five vertices a linear packing has at most two triples, and two must meet
once. The replayed K5 weights for 0/1/2 triples are 0/7/28; K5-e weights for
0/1 triples are 0/7. In K12, the number of two-triple five-sets is
12*C(5,2)=120. Triple/five-set incidences total 20*C(9,2)=720, giving
N1=480 and N0=C(12,5)-480-120=192. In K8-e there are 36 complete five-sets;
each of its two triples extends to C(5,2)-1=9 of these. Twenty five-sets
contain the missing edge's endpoints, and exactly two contain a triple.
Thus S5=7*(480+18+2)+28*120=6860 for EVERY legal realization.

Mixed-component intersections vanish: for m winners chosen hit triples use
3m distinct label pairs, requiring at least the least q with C(q,2)>=3m.
For every split of 5,6,7 tickets between components those two minima sum to
more than seven. On six clique vertices at most four contained triples are
possible (each vertex has degree <=2). Fewer than four give at most 14+b<18
hits using seven labels. Four force degree two at every vertex; the remaining
three edges form a matching. Exactly the four triple and three pair labels
win, so S6=7P, where P counts these Pasch six-sets and may vary by presentation.
On seven vertices, 21 hits require seven contained triples, a Fano subsystem.
Each of its seven vertices would need two additional triples on the other
five clique vertices. Those fourteen crossing triples consume distinct pairs
of five outside vertices, but C(5,2)=10. Hence S7=0. The near clique has only
two triples, so cannot contribute to S6 or S7.

Consequently Delta=135100+7P>=135100>=15595. Adopt the requested conservative
credit 15595, checked against this derived bound; no equality of P across
STS(13) presentations is assumed. Only the t=270 BOUND field changes. All
248 lower-t terms, S4=331240, cap authority, other rows and cursor persist.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_current_owner_motif_exact_refinement_r1 as previous
from .b649_k20_min_s2_three_motif_complete_family_integration_r1 import Ledger

integration, chase, split, event = (
    previous.integration,
    previous.chase,
    previous.split,
    previous.motif.event,
)
integer, object_row, rows, digest = (
    previous.integer,
    previous.object_row,
    previous.rows,
    previous.digest,
)
type Support = tuple[int, ...]
type Pair = tuple[int, int]
TASK_ID = "B649_K20_MIN_S2_STS13_HIGHER_ORDER_SLACK_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-sts13-higher-order-slack-certificate-r1"
BASE_HEAD = "f2ad83b4e07571a6842ac301d336360cec805a6a"
BASE_TREE = "0b089eb90884f14283679528be40295098a5d3ef"
BASE_RESULT_SHA256 = "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c"
PROFILE = integration.STS13_PROFILE
CAP = 270
REQUESTED_SLACK = 15_595
RESULT_FILENAME = "b649-k20-min-s2-sts13-higher-order-slack-certificate-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: Ledger
    sealed: dict[str, object]
    donor: dict[str, object]
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
    replay = previous.compute_result(inherited)
    if digest(replay) != digest(sealed):
        raise AssertionError("sealed predecessor replay differs")
    ledger = integration.install(
        inherited.ledger,
        previous.OWNER_PROFILE,
        integer(object_row(sealed["OWNER_CERTIFICATE"])["CERTIFIED_PROFILE_BOUND"]),
        f"{previous.RESULT_FILENAME}:OWNER_CERTIFICATE",
    )
    if integration.family(ledger, inherited.inherited.inherited) != sealed["FINAL_FAMILY"]:
        raise AssertionError("sealed complete family differs")
    donor = integration.pinned(
        integration.STS13_DONOR_HEAD,
        integration.STS13_RESULT_FILENAME,
        integration.STS13_DONOR_RESULT_SHA256,
    )
    provenance = {**inherited.provenance, relative: hashlib.sha256(blob).hexdigest()}
    return Authority(
        inherited, ledger, sealed, object_row(donor["STS13_T270_CERTIFICATE"]), provenance
    )


def excess_identity_check() -> dict[str, object]:
    """Pointwise proof on all allowed r, including the empty outcome."""
    table: list[list[int]] = []
    for r in range(8):
        s4, s5, s6, s7 = (comb(r, k) for k in range(4, 8))
        excess7 = 7 * (r - comb(r, 2) + comb(r, 3) - int(r > 0)) - 4 * s4
        if excess7 != 3 * s4 - 7 * s5 + 7 * s6 - 7 * s7 or s6 < s7 or excess7 < 0:
            raise AssertionError("higher-order excess identity failed")
        table.append([r, s4, s5, s6, s7, excess7])
    return {
        "STATUS": "PASS",
        "IDENTITY": "Delta = (3/7)S4 - S5 + S6 - S7",
        "TABLE": table,
        "R_CAP": comb(7, 2) // comb(3, 2),
        "S6_MINUS_S7_NONNEGATIVE": True,
    }


def local_profile(n: int, edges: set[Pair], triples: Sequence[Support]) -> tuple[int, ...]:
    """Exact projected label masks, including singleton and outside labels."""
    if not 4 <= n <= 7 or not edges <= set(combinations(range(n), 2)):
        raise ValueError("invalid induced graph")
    remaining = set(edges)
    masks: list[int] = []
    for triple in triples:
        if len(triple) != 3 or tuple(sorted(set(triple))) != triple:
            raise ValueError("invalid contained triple")
        covered = set(combinations(triple, 2))
        if not covered <= remaining:
            raise ValueError("nonlinear or unsupported triple")
        remaining -= covered
        masks.append(sum(1 << v for v in triple))
    masks.extend(sum(1 << v for v in pair) for pair in remaining)
    for v in range(n):
        used = sum(bool(mask & (1 << v)) for mask in masks)
        if used > 6:
            raise ValueError("ticket capacity exceeded")
        masks.extend([1 << v] * (6 - used))
    if len(masks) > 49:
        raise ValueError("pool capacity exceeded")
    counts = Counter(masks)
    counts[0] = 49 - len(masks)
    return tuple(counts[m] for m in range(1 << n))


@cache
def intersection_count(profile: tuple[int, ...]) -> int:
    """Exact |intersection E_j| via seven-label DP; seven special choices per set."""
    n = len(profile).bit_length() - 1
    if not 4 <= n <= 7 or len(profile) != 1 << n:
        raise ValueError("invalid intersection dimension")
    if any(type(c) is not int or c < 0 for c in profile) or sum(profile) != 49:
        raise ValueError("invalid label counts")
    if any(c and m.bit_count() > 3 for m, c in enumerate(profile)):
        raise ValueError("label support exceeds three tickets")
    if any(sum(c for m, c in enumerate(profile) if m & (1 << v)) != 6 for v in range(n)):
        raise ValueError("ticket capacity must be six")
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, (0,) * n): 1}
    for mask in sorted(range(len(profile)), key=int.bit_count, reverse=True):
        count = profile[mask]
        if not count:
            continue
        following: dict[tuple[int, tuple[int, ...]], int] = {}
        for (used, hits), ways in states.items():
            for take in range(min(count, 7 - used) + 1):
                new_hits = tuple(
                    min(3, h + take * bool(mask & (1 << v))) for v, h in enumerate(hits)
                )
                # A remaining label can supply at most three incidences.
                if sum(3 - h for h in new_hits) > 3 * (7 - used - take):
                    continue
                key = (used + take, new_hits)
                following[key] = following.get(key, 0) + ways * comb(count, take)
        states = following
    return 7 * states.get((7, (3,) * n), 0)


def linear_packings(n: int) -> list[tuple[Support, ...]]:
    """Exhaust ALL local linear triple systems on five or six vertices."""
    if n not in (5, 6):
        raise ValueError("local packing scope is five or six vertices")
    candidates = tuple(combinations(range(n), 3))
    max_blocks = n * ((n - 1) // 2) // 3
    return [
        p
        for b in range(max_blocks + 1)
        for p in combinations(candidates, b)
        if len({e for t in p for e in combinations(t, 2)}) == 3 * b
    ]


def universal_proof() -> dict[str, object]:
    """Finite induced-support checks plus universal double-counting identities."""
    table: list[list[int]] = []
    for packing in linear_packings(5):
        value = intersection_count(local_profile(5, set(combinations(range(5), 2)), packing))
        if value != (0, 7, 28)[len(packing)]:
            raise AssertionError("K5 label-support weight failed")
        table.append([5, len(packing), value])
    near = set(combinations(range(5), 2)) - {(0, 1)}
    for packing in ((), ((2, 3, 4),)):
        value = intersection_count(local_profile(5, near, packing))
        if value != 7 * len(packing):
            raise AssertionError("K5-e label-support weight failed")
        table.append([-5, len(packing), value])
    six_packings = linear_packings(6)
    for packing in six_packings:
        if len(packing) < 4:
            if 14 + len(packing) >= 18:
                raise AssertionError("six-ticket incidence exclusion failed")
            continue
        degrees = [sum(v in t for t in packing) for v in range(6)]
        value = intersection_count(local_profile(6, set(combinations(range(6), 2)), packing))
        if degrees != [2] * 6 or value != 7:
            raise AssertionError("Pasch support weight failed")
        table.append([6, len(packing), value])
    minima = [0] + [next(q for q in range(3, 8) if comb(q, 2) >= 3 * m) for m in range(1, 7)]
    splits = [[k, j, minima[j] + minima[k - j]] for k in (5, 6, 7) for j in range(1, k)]
    if any(row[2] <= 7 for row in splits):
        raise AssertionError("mixed-component exclusion failed")
    n2 = 12 * comb(5, 2)
    incidences = 20 * comb(9, 2)
    n1 = incidences - 2 * n2
    n0 = comb(12, 5) - n1 - n2
    near_complete = comb(8, 5) - comb(6, 3)
    near_one = 2 * (comb(5, 2) - 1)
    missing_one = 2
    s5 = 7 * (n1 + near_one + missing_one) + 28 * n2
    crossing = 7 * (5 - 3)
    outside_pairs = comb(12 - 7, 2)
    if crossing <= outside_pairs:
        raise AssertionError("Fano exclusion failed")
    s4 = 679 * (550 - 190) + 448 * 190 + 112 * 15
    numerator = 3 * s4 - 7 * s5
    if numerator % 7 or not 0 <= REQUESTED_SLACK <= numerator // 7:
        raise AssertionError("requested slack exceeds the universal premise")
    return {
        "STATUS": "PASS_UNIVERSAL_ALL_LEGAL_T270_REALIZATIONS",
        "S_DEFINITION": "Si = sum_{|Q|=i} intersection_count(Q) = sum_outcomes C(r,i)",
        "EXACT_S4": s4,
        "EXACT_S5": s5,
        "S6_FORMULA": "7 * PASCH_SIX_SET_COUNT",
        "EXACT_S7": 0,
        "PRESENTATION_DEPENDENT_PARAMETER": "PASCH_SIX_SET_COUNT >= 0",
        "K12_FIVE_SET_COUNTS_0_1_2": [n0, n1, n2],
        "K12_TRIPLE_FIVE_SET_INCIDENCES": incidences,
        "K8_MINUS_E_COMPLETE_FIVE_SET_COUNTS_0_1": [near_complete - near_one, near_one],
        "K8_MINUS_E_MISSING_FIVE_SET_COUNTS_0_1": [comb(6, 3) - missing_one, missing_one],
        "LOCAL_FIVE_PACKING_COUNT": len(linear_packings(5)),
        "LOCAL_SIX_PACKING_COUNT": len(six_packings),
        "LOCAL_PASCH_PACKING_COUNT": sum(len(p) == 4 for p in six_packings),
        "LOCAL_WEIGHT_TABLE": table,
        "LOCAL_WEIGHT_TABLE_SHA256": digest(table),
        "MIXED_COMPONENT_MIN_SELECTED_LABELS": splits,
        "FANO_REQUIRED_CROSSING_TRIPLES": crossing,
        "FANO_AVAILABLE_OUTSIDE_PAIRS": outside_pairs,
        "DELTA_FORMULA": "135100 + 7 * PASCH_SIX_SET_COUNT",
        "PROVED_SLACK_NUMERATOR_OVER_7": numerator,
        "PROVED_SLACK_LOWER_BOUND": numerator // 7,
        "CERTIFIED_SLACK": REQUESTED_SLACK,
    }


def higher_order_sums(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Exact S5/S6/S7 of a legal t=270 witness via induced support sets."""
    d = tuple(sum(v in t for t in triples) for v in range(20))
    chase.prior.r5.validate_k20_support_realization(triples, pairs, d)
    if "".join(map(str, sorted(d, reverse=True))) != PROFILE:
        raise ValueError("wrong STS13 degree profile")
    edges = {e for t in triples for e in combinations(t, 2)} | set(pairs)
    clique = tuple(v for v, degree in enumerate(d) if degree == 5)
    near = tuple(v for v in range(20) if v not in clique)
    zero = tuple(v for v in near if d[v] == 0)
    expected = set(combinations(clique, 2)) | (set(combinations(near, 2)) - {tuple(zero)})
    if edges != expected:
        raise ValueError("witness is not the isolated t270 graph")
    core = [set(t) for t in triples if set(t) <= set(clique)]
    if len(core) != 20 or sum(set(t) <= set(near) for t in triples) != 2:
        raise AssertionError("component label supports differ")
    histogram = Counter(sum(t <= set(q) for t in core) for q in combinations(clique, 5))
    if [histogram[b] for b in range(3)] != universal_proof()["K12_FIVE_SET_COUNTS_0_1_2"]:
        raise AssertionError("five-set label-support coverage failed")
    pasches = [list(q) for q in combinations(clique, 6) if sum(t <= set(q) for t in core) == 4]
    if any(sum(t <= set(q) for t in core) >= 7 for q in combinations(clique, 7)):
        raise AssertionError("illegal Fano subsystem")
    s5, s6, s7 = integer(universal_proof()["EXACT_S5"]), 7 * len(pasches), 0
    s3, _bound = chase.r20.bound_from_cap(split.profile_values(PROFILE), CAP, 331240)
    union = event.K20_S1 - event.K20_S2 + s3 - 331240 + s5 - s6 + s7
    return {
        "STATUS": "PASS",
        "S5": s5,
        "S6": s6,
        "S7": s7,
        "PASCH_SIX_SETS": pasches,
        "EXACT_ANY_PRIZE_UNION": union,
        "SUPPORTS_SHA256": digest([triples, pairs]),
    }


def traded_witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """One pair-preserving Pasch trade; a different legal STS13 presentation."""
    triples, pairs = split.witness_supports("STS13")
    q = set((0, 1, 2, 4, 7, 9))
    old = {t for t in triples if set(t) <= q}
    shadow = {e for t in old for e in combinations(t, 2)}
    new = {t for t in combinations(sorted(q), 3) if set(combinations(t, 2)) <= shadow} - old
    if len(old) != 4 or len(new) != 4 or {e for t in new for e in combinations(t, 2)} != shadow:
        raise AssertionError("Pasch trade failed to preserve label support")
    return tuple(sorted(set(triples) - old | new)), pairs


def owner_certificate(auth: Authority) -> dict[str, object]:
    row = auth.ledger[PROFILE]
    donor, proof = auth.donor, universal_proof()
    adoption = object_row(donor["ADOPTION"])
    iso = object_row(donor["GRAPH_ISOLATION"])
    terms = [list(rows(term)) for term in rows(adoption["ALL_T_TERMS"])]
    previous.exact_terms(split.profile_values(PROFILE), terms, CAP)
    if (
        type(row.cap) is not int
        or (row.cap, row.source, row.bound, row.s4_base)
        != (CAP, integration.STS13_LOCATOR, adoption["FULL_PROFILE_BOUND"], adoption["S4_BASE"])
        or iso["STATUS"] != "PROVED_UNIQUE"
        or iso["STRUCTURE"] != "K12 + (K8-e)"
    ):
        raise AssertionError("t270 cap-source or graph identity mismatch")
    lower, last = terms[:-1], terms[-1]
    if last[4] != proof["EXACT_S4"] or max(integer(t[1]) for t in terms) != row.bound:
        raise AssertionError("sealed STS13 envelope mismatch")
    new_bound = integer(last[1]) - integer(proof["CERTIFIED_SLACK"])
    new_terms = [*lower, [last[0], new_bound, *last[2:]]]
    return {
        "PROFILE_ID": PROFILE,
        "LOAD_BEARING_T": CAP,
        "EXACT_S4": last[4],
        "CAP_SOURCE": adoption["CAP_AUTHORITY"],
        "CAP_SOURCE_IDENTITY": adoption["CAP_AUTHORITY"],
        "EXISTING_LEDGER_SOURCE": row.source,
        "DONOR_CERTIFICATE_SHA256": digest(donor),
        "HIGHER_ORDER_PROOF": proof,
        "CERTIFIED_SLACK": proof["CERTIFIED_SLACK"],
        "OLD_T270_BOUND": last[1],
        "NEW_T270_BOUND": new_bound,
        "RETAINED_LOWER_T_COUNT": len(lower),
        "RETAINED_LOWER_T_MAX": max(integer(t[1]) for t in lower),
        "RETAINED_TERMS_SHA256": digest(lower),
        "ALL_T_TERMS": new_terms,
        "CERTIFIED_PROFILE_BOUND": max(integer(t[1]) for t in new_terms),
        "STATUS": "PASS",
    }


def verify_certificate(cert: Mapping[str, object], auth: Authority) -> None:
    if digest(cert) != digest(owner_certificate(auth)):
        raise AssertionError("tampered higher-order certificate")


def witness_soundness(bound: int, auth: Authority) -> dict[str, object]:
    """Guard legal unions; the historical Routes 1-4 capability is superseded here."""
    named = {
        "CYCLIC_STS13": higher_order_sums(*split.witness_supports("STS13")),
        "TRADED_STS13": higher_order_sums(*traded_witness()),
    }
    sealed_witness = object_row(auth.inherited.inherited.r30["SOUNDNESS_WITNESS"])
    if named["CYCLIC_STS13"]["EXACT_ANY_PRIZE_UNION"] != sealed_witness["EXACT_ANY_PRIZE_UNION"]:
        raise AssertionError("exact witness union differs from pinned official union")
    if any(bound < integer(w["EXACT_ANY_PRIZE_UNION"]) for w in named.values()):
        raise AssertionError("new bound drops below a legal witness union")
    return {
        "STATUS": "PASS",
        "CHECKED_BOUND": bound,
        "WITNESSES": named,
        "INHERITED_WITNESS_SOUNDNESS": auth.sealed["WITNESS_SOUNDNESS"],
        "HISTORICAL_ROUTES_1_TO_4_CAPABILITY_RETAINED": True,
        "ACCEPTANCE_RULE": "NEW_BOUND >= EXACT_OFFICIAL_UNION_OF_EACH_LEGAL_WITNESS",
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    cert = owner_certificate(auth)
    verify_certificate(cert, auth)
    final = integration.install(
        auth.ledger,
        PROFILE,
        integer(cert["CERTIFIED_PROFILE_BOUND"]),
        f"{RESULT_FILENAME}:OWNER_CERTIFICATE",
    )
    if {pid for pid in final if final[pid] != auth.ledger[pid]} != {PROFILE}:
        raise AssertionError("only the STS13 row may change")
    start = integration.family(auth.ledger, auth.inherited.inherited.inherited)
    family = integration.family(final, auth.inherited.inherited.inherited)
    if (start["CURSOR_ID"], start["CURSOR_BOUND"], start["COVERAGE"]) != (
        family["CURSOR_ID"],
        family["CURSOR_BOUND"],
        family["COVERAGE"],
    ):
        raise AssertionError("cursor authority or profile coverage changed")
    soundness = witness_soundness(integer(cert["NEW_T270_BOUND"]), auth)
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
        "HIGHER_ORDER_IDENTITY": excess_identity_check(),
        "HIGHER_ORDER_IDENTITY_STATUS": "PASS",
        "UNIVERSAL_SLACK_PROOF_STATUS": "PASS",
        "OWNER_CERTIFICATE": cert,
        "EXACT_S4": cert["EXACT_S4"],
        "S5_S6_S7_EVIDENCE": cert["HIGHER_ORDER_PROOF"],
        "CERTIFIED_SLACK": cert["CERTIFIED_SLACK"],
        "OLD_T270_BOUND": cert["OLD_T270_BOUND"],
        "NEW_T270_BOUND": cert["NEW_T270_BOUND"],
        "RETAINED_LOWER_T_MAX": cert["RETAINED_LOWER_T_MAX"],
        "FINAL_PROFILE_BOUND": cert["CERTIFIED_PROFILE_BOUND"],
        "START_FAMILY": start,
        "FINAL_FAMILY": family,
        "START_COMPLETE_FAMILY_UB": start["FAMILY_UB"],
        "FINAL_COMPLETE_FAMILY_UB": family["FAMILY_UB"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "REMAINING_GAP": family["REMAINING_GAP"],
        "OTHER_PROFILE_ROWS_UNCHANGED": len(final) - 1,
        "OTHER_ROWS_SHA256": digest({pid: r.bound for pid, r in final.items() if pid != PROFILE}),
        "INHERITED_CERTIFICATES": auth.sealed["INHERITED_CERTIFICATES"],
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "WITNESS_SOUNDNESS": soundness,
        "WITNESS_SOUNDNESS_STATUS": soundness["STATUS"],
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
        raise AssertionError("tampered immutable higher-order result")


def main() -> None:
    if RESULT_PATH.exists():
        raise AssertionError("immutable higher-order result already exists")
    result = compute_result()
    with RESULT_PATH.open("x", encoding="utf-8") as out:
        out.write(integration.render(result))
    print(json.dumps({k: result[k] for k in ("FINAL_COMPLETE_FAMILY_UB", "REMAINING_GAP")}))


if __name__ == "__main__":
    main()
