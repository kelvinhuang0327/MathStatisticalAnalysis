"""Complete resolved Bonferroni-5 and cursor Route-B refinement, without a solver.

The immutable dbc4c14d result and its executable predecessor are replayed.
Recover all 4647 rows, including their original cap authorities and the 25
special per-t certificates. A certified motif floor is used only at its
certified t; lower-t terms and existing fifth-order terms retain their own
authority. Caps come from NB/R18, sealed R30 refutations, the sealed R25/R13
relaxation, or the sealed zero/core split. No R25/R30 execution is performed.

For 22 pair-linear triple supports, graph degrees are g=6+d. A support tau
has m_tau <= 4+min(d_v). For H_k supports on vertices of degree >=k,
3H_k <= sum_{d>=k}d, H_k <= 22-d_v for each positive low vertex, and
H_k=0 with fewer than three high vertices. Threshold telescoping bounds
sum_tau C(m_tau,2). Pair-linearity gives N_2T <= sum_v C(d_v,2).
The inherited exact identity is S5=7*(sum_tau C(m_tau,2)+2*N_2T);
a double-triple K5 has weight 28. These caps are independent of t.
At every legal t, odd-order Bonferroni gives B5=S1-S2+S3-S4_used+S5_cap.
Take min(EXISTING_TERM,B5), then max over ALL legal t, never add credits.

Recover the 197 W=774..785 histograms by bounded degree-class lookup and
match the sealed partition digest. Their legal range is 22..floor(W/3).
Route B uses K4>=max(0,ceil((J-(max(g)-2)*(W-3t))/4)), A<=floor(B/3),
S4>=max(profile floor,448*min(K4,A)+679*(K4-min(K4,A))). Its fourth-order
bound is ceil(S1-S2+S3-4*S4/7). All ceilings and floors are exact integers.
The frontier envelope replaces the CURSOR authority slot, including when
it is below the incumbent. It never enters the resolved-row ledger.

Each profile records hashes of its complete ordered integer term lists,
their counts, maxima and maximizing t. The executable verifier regenerates
every term. Special source lists remain sealed and are preserved separately.
Resolved and frontier ids must be disjoint, exhaustive, digest-matched to
the inherited 4844-profile partition. Recompute both maxima and their union.
Every recorded support witness, P2 and STS13 is checked against the actual
new per-t envelope. Historical source/result bytes remain immutable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from itertools import combinations
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_active_seven_all_t_bonferroni5_r1 as previous
from .b649_k20_min_s2_nb_degree_cap_frontier_r1 import CapAuthorities
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Authority as FamilyAuthority
from .b649_k20_min_s2_split_cap_current_owner_chase_r1 import Row

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
nb, motif, identity = previous.nb, previous.motif, previous.identity
moment_bounds = previous.moment_bounds
TASK_ID = "B649_K20_MIN_S2_ALL_RESOLVED_CURSOR_REFINEMENT_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-all-resolved-cursor-refinement-r1"
BASE_HEAD = "dbc4c14d71eeb855920e973cfd8e859ca6041e7b"
BASE_TREE = "645862ea86c5f35bc279e4f88b7b4f1a318fa5e5"
BASE_RESULT_SHA256 = "d97bf13bcaa445b6121b16e98778476621a53c612fcf0a2159f1bc110fe13762"
FRONTIER_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
ADMISSIBLE_SHA256 = "11686dabb0173393a1730efe287da93bed5334e8c942b24f46bdb45ef1dc8893"
RESULT_FILENAME = "b649-k20-min-s2-all-resolved-cursor-refinement-r1-result.json"
RESULT_PATH = chase.ROOT / chase.prior.RESULT_DIRECTORY / RESULT_FILENAME
INCUMBENT = 313263888
START_BOUND = 313394584
CAP_COUNTS = {"NB_R18": 4579, "R30_REFUTATION": 51, "R25_R13": 1, "ZERO_CORE_SPLIT": 16}
type Term = tuple[int, int, int, int | None, int, int]
type Profile = tuple[int, ...]


@dataclass(frozen=True)
class Authority:
    inherited: previous.Authority
    ledger: dict[str, Row]
    cap_ledger: dict[str, Row]
    family_authority: FamilyAuthority
    sealed: dict[str, object]
    special: dict[str, dict[str, object]]
    cap_proofs: dict[str, dict[str, object]]
    cap_proof_sha256: dict[str, str]
    frontier: tuple[str, ...]
    provenance: dict[str, str]
    result_provenance: dict[str, str]


def profile_values(profile: str | Sequence[int]) -> Profile:
    """Minimum-S2 degrees, including profiles with no zero-degree vertex."""
    d = tuple(map(int, profile)) if isinstance(profile, str) else tuple(profile)
    if len(d) != 20 or sum(d) != 66 or any(type(v) is not int or not 0 <= v <= 6 for v in d):
        raise ValueError("expected twenty integer degrees in 0..6 with sum 66")
    return tuple(sorted(d, reverse=True))


def degree_s5_cap(profile: str | Sequence[int]) -> dict[str, object]:
    """Degree-only threshold proof on the full admissible profile domain."""
    d = profile_values(profile)
    thresholds: list[list[int]] = []
    for k in range(1, 7):
        high = [v for v in d if v >= k]
        low = [v for v in d if 0 < v < k]
        incidence = sum(high) // 3 if len(high) >= 3 else 0
        low_vertex = 22 - max(low, default=0)
        thresholds.append(
            [k, len(high), sum(high), incidence, low_vertex, min(incidence, low_vertex)]
        )
    weights = [comb(4 + k, 2) for k in range(1, 7)]
    common_cap = 22 * weights[0] + sum(
        thresholds[k - 1][5] * (weights[k - 1] - weights[k - 2]) for k in range(2, 7)
    )
    n2_cap = sum(comb(v, 2) for v in d)
    return {
        "STATUS": "PASS",
        "D": list(d),
        "G": [6 + v for v in d],
        "M_TAU_CAP": "4 + min(d_v for v in tau)",
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


def row_identity(pid: str, row: Row) -> list[object]:
    return [pid, row.bound, row.cap, row.s4_base, row.source, row.realization]


def pinned_file(relative: str) -> bytes:
    blob = chase.git("show", f"{BASE_HEAD}:{relative}")
    if (chase.ROOT / relative).read_bytes() != blob:
        raise AssertionError(f"immutable source/result bytes differ: {relative}")
    return blob


def source_certificate(locator: str, provenance: dict[str, str]) -> dict[str, object]:
    """Resolve a sealed JSON slot; conceptual NB rows are not used as JSON slots."""
    filename, slot = locator.split(":", 1)
    if not re.fullmatch(r"b649-k20-min-s2-[a-z0-9-]+-result\.json", filename):
        raise AssertionError("invalid certificate filename")
    relative = f"{chase.prior.RESULT_DIRECTORY}/{filename}"
    blob = pinned_file(relative)
    provenance[relative] = hashlib.sha256(blob).hexdigest()
    value: object = object_row(json.loads(blob))
    tokens = re.findall(r"[A-Z][A-Z0-9_]*|\[[0-9]+\]", slot)
    if "".join(tokens) != slot:
        raise AssertionError("invalid certificate slot")
    for token in tokens:
        if token.startswith("["):
            key = token[1:-1]
            value = (
                cast(list[object], value)[int(key)]
                if isinstance(value, list)
                else object_row(value)[key]
            )
        else:
            value = object_row(value)[token]
    return object_row(value)


def recover_frontier(base: Mapping[str, object]) -> tuple[str, ...]:
    partition = object_row(base["INHERITED_PARTITION"])
    sealed = object_row(partition[chase.prior.PART_FRONTIER])
    if sealed != {"COUNT": 197, "IDS_SHA256": FRONTIER_SHA256, "W_RANGE": [774, 785]}:
        raise AssertionError("sealed frontier partition identity mismatch")
    found = tuple(
        chase.profile_id(p)
        for w in range(774, 786)
        for p in nb.enumerate_degree_square_class(2 * w - 1326)
    )
    return tuple(sorted(found))


def partition_check(
    ledger: Mapping[str, Row], frontier: Sequence[str], authority: FamilyAuthority
) -> dict[str, object]:
    coverage = chase.coverage(ledger, authority.members, authority.base)
    member_ids = [chase.profile_id(p) for part in authority.members.values() for p in part]
    frontier_profiles = tuple(profile_values(pid) for pid in frontier)
    all_profiles = [*(profile_values(pid) for pid in ledger), *frontier_profiles]
    if (
        len(member_ids) != len(set(member_ids))
        or set(member_ids) != set(ledger)
        or len(ledger) != 4647
        or len(frontier) != len(set(frontier))
        or len(frontier) != 197
        or set(ledger) & set(frontier)
        or chase.prior.CURSOR_ID in ledger
        or chase.prior.CURSOR_ID not in frontier
        or any(not 774 <= nb.overlap_wedge_count(p) <= 785 for p in frontier_profiles)
        or chase.prior.ids_digest(frontier_profiles) != FRONTIER_SHA256
        or len(all_profiles) != 4844
        or chase.prior.ids_digest(all_profiles) != ADMISSIBLE_SHA256
    ):
        raise AssertionError("resolved/frontier partition missing, duplicated or tampered")
    return {
        **coverage,
        "FRONTIER_IDS_SHA256": FRONTIER_SHA256,
        "ADMISSIBLE_IDS_SHA256": ADMISSIBLE_SHA256,
        "DISJOINT_EXHAUSTIVE": True,
    }


def recover_cap_proof(
    pid: str,
    row: Row,
    authorities: CapAuthorities,
    result_provenance: dict[str, str],
) -> dict[str, object]:
    p = profile_values(pid)
    w, ow, nb_cap = nb.profile_nb_cap(p)
    r18 = nb.r18_cap(p)
    common: dict[str, object] = {
        "PROFILE_ID": pid,
        "TRIANGLE_CAP": row.cap,
        "ORIGINAL_CAP_LOCATOR": row.source,
        "W": w,
        "NB_OPEN_WEDGE_FLOOR": ow,
        "NB_CAP": nb_cap,
        "R18_CAP": r18,
    }
    if row.s4_base != nb.r28.profile_s4_floor(p) or not 22 <= row.cap <= w // 3:
        raise AssertionError("profile S4 base or cap domain differs")
    filename = row.source.split(":", 1)[0]
    if filename in (split.RESULT_FILENAME, chase.RESULT_FILENAME):
        cert = source_certificate(row.source, result_provenance)
        derived = split.split_certificate(p)
        if (
            cert["PROFILE_ID"] != pid
            or cert["TRIANGLE_CAP"] != row.cap
            or cert.get("SPLIT_TRIANGLE_CAP", row.cap) != derived["TRIANGLE_CAP"]
            or cert.get("SPLIT_BRANCH_COUNTS", cert.get("BRANCH_COUNTS"))
            != derived["BRANCH_COUNTS"]
            or row.cap
            != min(
                integer(derived["TRIANGLE_CAP"]),
                integer(cert.get("EXISTING_TRIANGLE_CAP", row.cap)),
            )
        ):
            raise AssertionError("sealed zero/core cap provenance mismatch")
        return {**common, "CLASS": "ZERO_CORE_SPLIT", "IDENTITY": derived}
    if row.cap >= min(nb_cap, r18):
        return {**common, "CLASS": "NB_R18", "VALID_CAP": min(nb_cap, r18)}
    for index, proof in enumerate(authorities.proofs):
        if (
            proof.get("STATUS") == "INFEASIBLE"
            and proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") == row.cap
            and pid in rows(proof.get("PROFILE_IDS", []))
        ):
            if (
                proof.get("ATTEMPT_INDEX") != index
                or nb.r28.r26.accepted_cap(proof, (p,), row.cap) != row.cap
            ):
                raise AssertionError("sealed R30 cap provenance mismatch")
            return {
                **common,
                "CLASS": "R30_REFUTATION",
                "CAP_SOURCE": f"{nb.R30_RESULT}:GROUP_ATTEMPTS[{index}]",
                "IDENTITY": dict(proof),
            }
    for index, cert in enumerate(authorities.cheap):
        if cert.get("PROFILE_ID") == pid:
            envelope = object_row(cert["PROFILE_ENVELOPE"])
            relaxation = object_row(cert["R13_RELAXATION"])
            if (
                envelope["GRAPH_TRIANGLE_UPPER_BOUND"] == row.cap
                and relaxation["SOLVER_STATUS"] == "OPTIMAL"
            ):
                return {
                    **common,
                    "CLASS": "R25_R13",
                    "CAP_SOURCE": f"{nb.R25_RESULT}:CHEAP_CERTIFICATES[{index}]",
                    "IDENTITY": dict(cert),
                }
    raise AssertionError(f"no valid sealed cap authority: {pid}")


@cache
def load_authority() -> Authority:
    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("immutable base tree mismatch")
    sealed = integration.pinned(BASE_HEAD, previous.RESULT_FILENAME, BASE_RESULT_SHA256)
    relative = Path(previous.__file__ or "").resolve().relative_to(chase.ROOT).as_posix()
    source = pinned_file(relative)
    if hashlib.sha256(source).hexdigest() != sealed["SOURCE_SHA256"]:
        raise AssertionError("immutable predecessor source identity mismatch")
    inherited = previous.load_authority()
    if digest(previous.compute_result(inherited)) != digest(sealed):
        raise AssertionError("immutable predecessor executable replay mismatch")
    ledger = dict(inherited.ledger)
    for pid, raw in object_row(sealed["PROFILE_CERTIFICATES"]).items():
        cert = object_row(raw)
        ledger[pid] = replace(
            ledger[pid],
            bound=integer(cert["CERTIFIED_PROFILE_BOUND"]),
            source=f"{previous.RESULT_FILENAME}:PROFILE_CERTIFICATES[{pid}]",
        )
    family_authority = inherited.family_authority
    if integration.family(ledger, family_authority) != sealed["FINAL_FAMILY"]:
        raise AssertionError("latest sealed resolved ledger differs")
    provenance = {**inherited.provenance, relative: hashlib.sha256(source).hexdigest()}
    for path, expected in provenance.items():
        if hashlib.sha256(pinned_file(path)).hexdigest() != expected:
            raise AssertionError("inherited module provenance differs")
    result_provenance: dict[str, str] = {}
    for filename, expected in ((nb.R30_RESULT, nb.R30_SHA256), (nb.R25_RESULT, nb.R25_SHA256)):
        relative = f"{chase.prior.RESULT_DIRECTORY}/{filename}"
        observed = hashlib.sha256(pinned_file(relative)).hexdigest()
        if observed != expected:
            raise AssertionError("immutable R30/R25 cap result identity mismatch")
        result_provenance[relative] = observed
    cap_ledger = integration.chase_ledger(
        family_authority,
        motif.pinned_result(chase.RESULT_FILENAME, integration.CHASE_RESULT_SHA256),
    )
    special: dict[str, dict[str, object]] = {}
    for pid, row in ledger.items():
        original = cap_ledger[pid]
        if (row.cap, row.s4_base, row.realization) != (
            original.cap,
            original.s4_base,
            original.realization,
        ):
            raise AssertionError("inherited cap/S4/witness authority changed")
        if row != original:
            special[pid] = source_certificate(row.source, result_provenance)
    if len(special) != 25:
        raise AssertionError("special per-t certificate coverage differs")
    authorities = nb.load_cap_authorities()
    cap_proofs = {
        pid: recover_cap_proof(pid, row, authorities, result_provenance)
        for pid, row in sorted(cap_ledger.items())
    }
    if Counter(integration.text(proof["CLASS"]) for proof in cap_proofs.values()) != CAP_COUNTS:
        raise AssertionError("sealed cap provenance class counts differ")
    for pid, proof in cap_proofs.items():
        proof["ROW_IDENTITY_SHA256"] = digest(row_identity(pid, ledger[pid]))
        proof["SPECIAL_CERTIFICATE_SHA256"] = digest(special[pid]) if pid in special else None
    frontier = recover_frontier(family_authority.base)
    partition_check(ledger, frontier, family_authority)
    return Authority(
        inherited,
        ledger,
        cap_ledger,
        family_authority,
        sealed,
        special,
        cap_proofs,
        {pid: digest(proof) for pid, proof in cap_proofs.items()},
        frontier,
        provenance,
        result_provenance,
    )


def assert_row(auth: Authority, pid: str) -> Row:
    row = auth.ledger[pid]
    proof = auth.cap_proofs[pid]
    if (
        proof["PROFILE_ID"] != pid
        or proof["TRIANGLE_CAP"] != row.cap
        or proof["ROW_IDENTITY_SHA256"] != digest(row_identity(pid, row))
        or row.cap != auth.cap_ledger[pid].cap
        or proof["ORIGINAL_CAP_LOCATOR"] != auth.cap_ledger[pid].source
        or digest(proof) != auth.cap_proof_sha256[pid]
    ):
        raise AssertionError("sealed row/cap/source identity mismatch")
    return row


def parse_term(raw: object) -> Term:
    """Keep the sealed motif's unspecified contained-K4 cap as null."""
    fields = rows(raw)
    if len(fields) != 6:
        raise AssertionError("expected six sealed term fields")
    t, b, k, a, s4, s3 = fields
    return (
        integer(t),
        integer(b),
        integer(k),
        None if a is None else integer(a),
        integer(s4),
        integer(s3),
    )


def authoritative_terms(auth: Authority, pid: str) -> list[Term]:
    row = assert_row(auth, pid)
    p = profile_values(pid)
    generic = split.route_b_terms(p, row.cap, row.s4_base)
    if pid not in auth.special:
        old = generic
    else:
        cert = auth.special[pid]
        adoption = object_row(cert["ADOPTION"]) if "ADOPTION" in cert else cert
        if cert.get("LOAD_BEARING_T", cert.get("TRIANGLE_CAP", row.cap)) != row.cap:
            raise AssertionError("special S4 certificate t applicability differs")
        old = [parse_term(raw) for raw in rows(adoption["ALL_T_TERMS"])]
        if cert.get("PROFILE_ID") != pid or len(old) != len(generic):
            raise AssertionError("special certificate profile/t coverage differs")
        for before, baseline in zip(old, generic, strict=True):
            if len(before) != 6 or before[0] != baseline[0] or before[5] != baseline[5]:
                raise AssertionError("special certificate t/S3 identity differs")
            # Every inherited motif refinement is scoped to this row's cap t.
            if before[0] != row.cap and before[2:] != baseline[2:]:
                raise AssertionError("special S4 floor leaked outside certified t")
            if before[4] < baseline[4]:
                raise AssertionError("special floor weakened its inherited authority")
        if digest(cert) != auth.cap_proofs[pid]["SPECIAL_CERTIFICATE_SHA256"]:
            raise AssertionError("sealed special per-t certificate identity differs")
    terms = [(t, b, k, a, s4, s3) for t, b, k, a, s4, s3 in old]
    if [term[0] for term in terms] != list(range(22, row.cap + 1)):
        raise AssertionError("incomplete legal t envelope")
    if max(term[1] for term in terms) != row.bound:
        raise AssertionError("per-t envelope does not reproduce sealed row")
    return terms


def refine_terms(old: Sequence[Term], s5: int) -> tuple[list[Term], list[list[int]]]:
    new: list[Term] = []
    fifths: list[list[int]] = []
    for t, bound, k, a, s4, s3 in old:
        fourth, fifth = moment_bounds(s3, s4, s5)
        if (
            bound > fourth
            or not 0 <= 7 * fourth - (7 * (event.K20_S1 - event.K20_S2 + s3) - 4 * s4) < 7
        ):
            raise AssertionError("existing moment bound or integer ceiling differs")
        new.append((t, min(bound, fifth), k, a, s4, s3))
        fifths.append([t, fifth])
    return new, fifths


def resolved_certificate(auth: Authority, pid: str) -> dict[str, object]:
    row = assert_row(auth, pid)
    old = authoritative_terms(auth, pid)
    s5_proof = degree_s5_cap(pid)
    new, fifths = refine_terms(old, integer(s5_proof["S5_CAP"]))
    maximum = max(term[1] for term in new)
    return {
        "PROFILE_ID": pid,
        "OLD_PROFILE_BOUND": row.bound,
        "EXISTING_TERM_SOURCE": row.source,
        "CAP_AUTHORITY": auth.cap_proofs[pid],
        "S4_BASE": row.s4_base,
        "SPECIAL_CERTIFICATE_SHA256": digest(auth.special[pid]) if pid in auth.special else None,
        "S4_SCOPE": "SEALED_PER_T; SPECIAL_MOTIF_ONLY_AT_CERTIFIED_T",
        "DEGREE_S5_PROOF": s5_proof,
        "S5_SCOPE": "EVERY_LEGAL_T_DEGREE_ONLY",
        "T_RANGE": [22, row.cap],
        "LEGAL_T_COUNT": len(new),
        "AUTHORITATIVE_TERMS_SHA256": digest(old),
        "ALL_T_TERMS_SHA256": digest(new),
        "BONFERRONI5_TERMS_SHA256": digest(fifths),
        "CHANGED_T_TERM_COUNT": sum(a[1] != b[1] for a, b in zip(old, new, strict=True)),
        "CERTIFIED_PROFILE_BOUND": maximum,
        "ARGMAX_T": [term[0] for term in new if term[1] == maximum],
        "CAP_T_NEW_BOUND": new[-1][1],
        "BOUND_RULE": "MIN(EXISTING_TERM,B5); MAX_OVER_ALL_LEGAL_T",
    }


def frontier_certificate(pid: str) -> dict[str, object]:
    p = profile_values(pid)
    w = nb.overlap_wedge_count(p)
    if not 774 <= w <= 785:
        raise AssertionError("profile outside sealed frontier W range")
    cap = w // 3
    base = nb.r28.profile_s4_floor(p)
    terms = split.route_b_terms(p, cap, base)
    maximum = max(term[1] for term in terms)
    return {
        "PROFILE_ID": pid,
        "W": w,
        "TRIANGLE_CAP": cap,
        "CAP_AUTHORITY": "THREE_CLOSED_WEDGES_PER_TRIANGLE; FLOOR(W/3)",
        "S4_BASE": base,
        "T_RANGE": [22, cap],
        "LEGAL_T_COUNT": len(terms),
        "ALL_T_TERMS_SHA256": digest(terms),
        "CERTIFIED_PROFILE_BOUND": maximum,
        "ARGMAX_T": [term[0] for term in terms if term[1] == maximum],
        "ROUTE": "GENERIC_ROUTE_B_ALL_T",
    }


def install_resolved(
    ledger: Mapping[str, Row], pid: str, cert: Mapping[str, object]
) -> dict[str, Row]:
    old = ledger[pid]
    bound = integer(cert["CERTIFIED_PROFILE_BOUND"])
    if cert["PROFILE_ID"] != pid or not 0 <= bound <= old.bound:
        raise AssertionError("invalid resolved profile refinement")
    return {
        **ledger,
        pid: old
        if bound == old.bound
        else replace(old, bound=bound, source=f"{RESULT_FILENAME}:RESOLVED_CERTIFICATES[{pid}]"),
    }


def family(
    ledger: Mapping[str, Row], frontier: Mapping[str, object], auth: Authority
) -> dict[str, object]:
    coverage = partition_check(ledger, tuple(frontier), auth.family_authority)
    resolved_bounds = {pid: row.bound for pid, row in ledger.items()}
    frontier_bounds = {
        pid: integer(object_row(cert)["CERTIFIED_PROFILE_BOUND"]) for pid, cert in frontier.items()
    }
    if any(object_row(frontier[pid])["PROFILE_ID"] != pid for pid in frontier):
        raise AssertionError("frontier certificate identity differs")
    resolved_max = max(resolved_bounds.values())
    cursor_bound = max(frontier_bounds.values())
    complete = {**resolved_bounds, **frontier_bounds}
    maximum = max(resolved_max, cursor_bound)
    if maximum != max(complete.values()) or not INCUMBENT <= maximum <= START_BOUND:
        raise AssertionError("complete Family maximum or incumbent interval differs")
    return {
        "FAMILY_UB": maximum,
        "OWNER_IDS": sorted(pid for pid, value in complete.items() if value == maximum),
        "RESOLVED_MAX": resolved_max,
        "RESOLVED_OWNER_IDS": sorted(
            pid for pid, value in resolved_bounds.items() if value == resolved_max
        ),
        "CURSOR_AUTHORITY": {
            "SLOT": "CURSOR",
            "CURSOR_ID": chase.prior.CURSOR_ID,
            "OLD_BOUND": START_BOUND,
            "BOUND": cursor_bound,
            "PROFILE_COUNT": len(frontier),
            "PROFILE_IDS_SHA256": FRONTIER_SHA256,
            "MAXIMIZER_IDS": sorted(
                pid for pid, value in frontier_bounds.items() if value == cursor_bound
            ),
        },
        "COVERAGE": coverage,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": maximum - INCUMBENT,
        "RESOLVED_ROWS_SHA256": digest(
            [row_identity(pid, row) for pid, row in sorted(ledger.items())]
        ),
    }


def witness_soundness(
    auth: Authority, ledger: Mapping[str, Row], certs: Mapping[str, object]
) -> dict[str, object]:
    # The predecessor checks every recorded support with the exact local moment table.
    witnesses = previous.witness_soundness(ledger, {})
    seen = object_row(witnesses["WITNESSES"])
    extras = {kind: split.witness_supports(kind) for kind in ("CONDITIONAL", "TOP")}
    extras["TRADED_STS13"] = identity.previous.traded_witness()
    for name, supports in extras.items():
        triples, pairs = supports
        observed = motif.realization_check(triples, pairs)
        pid = integration.text(observed["PROFILE_ID"])
        edges = {e for tau in triples for e in combinations(tau, 2)} | set(pairs)
        common, n2 = identity.s5_counts(tuple(range(20)), edges, triples)
        s5 = identity.s5_identity_value(common, n2)
        s3, _bound = chase.r20.bound_from_cap(
            profile_values(pid), integer(observed["TRIANGLES"]), 0
        )
        seen[name] = {
            **observed,
            "EXACT_S5": s5,
            "M_TAU": list(common),
            "N_2T": n2,
            "EXACT_MOMENT_UPPER_BOUND": min(
                moment_bounds(s3, integer(observed["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]), s5)
            ),
            "SUPPORTS_SHA256": digest(supports),
        }
    for name, raw in seen.items():
        witness = object_row(raw)
        pid, t = integration.text(witness["PROFILE_ID"]), integer(witness["TRIANGLES"])
        cert = object_row(certs[pid])
        old = authoritative_terms(auth, pid)
        terms, _fifths = refine_terms(old, integer(object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"]))
        if (
            not 22 <= t <= auth.ledger[pid].cap
            or integer(witness["EXACT_S5"]) > integer(object_row(cert["DEGREE_S5_PROOF"])["S5_CAP"])
            or integer(witness["EXACT_S4_FROM_PINNED_LOCAL_TABLE"]) < terms[t - 22][4]
            or integer(witness["EXACT_MOMENT_UPPER_BOUND"]) > terms[t - 22][1]
            or integer(witness["EXACT_MOMENT_UPPER_BOUND"]) > ledger[pid].bound
        ):
            raise AssertionError(f"refined envelope excludes a legal support witness: {name}")
    if len(seen) != 77 or ledger[integration.STS13_PROFILE].bound < INCUMBENT:
        raise AssertionError("witness coverage or incumbent soundness differs")
    traded = identity.previous.higher_order_sums(*extras["TRADED_STS13"])
    if traded["EXACT_ANY_PRIZE_UNION"] != INCUMBENT:
        raise AssertionError("exact incumbent support witness differs")
    return {
        **witnesses,
        "WITNESSES": seen,
        "WITNESS_COUNT": len(seen),
        "ALL_REFINED_ENVELOPES_STATUS": "PASS",
        "TRADED_STS13_EXACT_UNION": traded,
    }


def compute_result(authority: Authority | None = None) -> dict[str, object]:
    auth = load_authority() if authority is None else authority
    partition_check(auth.ledger, auth.frontier, auth.family_authority)
    resolved: dict[str, object] = {}
    final = dict(auth.ledger)
    for pid in sorted(auth.ledger):
        cert = resolved_certificate(auth, pid)
        resolved[pid] = cert
        final = install_resolved(final, pid, cert)
    frontier: dict[str, object] = {pid: frontier_certificate(pid) for pid in auth.frontier}
    final_family = family(final, frontier, auth)
    cursor = object_row(final_family["CURSOR_AUTHORITY"])
    above = sorted(pid for pid, row in final.items() if row.bound > INCUMBENT)
    changed = sum(final[pid].bound != row.bound for pid, row in auth.ledger.items())
    soundness = witness_soundness(auth, final, resolved)
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
        "RESULT_PROVENANCE": auth.result_provenance,
        "PROOF": __doc__,
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4_CAP", "S4", "S3"],
        "TERM_HASH_ENCODING": "CANONICAL_JSON_DIGEST; UNSPECIFIED_SEALED_MOTIF_A_KEPT_NULL",
        "S5_IDENTITY": auth.sealed["S5_IDENTITY"],
        "BONFERRONI5": identity.bonferroni_check(),
        "CAP_PROVENANCE_COUNTS": dict(
            sorted(Counter(integration.text(p["CLASS"]) for p in auth.cap_proofs.values()).items())
        ),
        "CAP_PROVENANCE_STATUS": "PASS_SEALED_SOURCES_AND_ALL_PROFILE_DOMAINS",
        "SPECIAL_PER_T_PROFILE_COUNT": len(auth.special),
        "SPECIAL_PER_T_CERTIFICATES": auth.special,
        "SPECIAL_S4_SCOPE_STATUS": "PASS_CERTIFIED_T_ONLY",
        "S5_ALL_T_SOUNDNESS_STATUS": "PASS_DEGREE_ONLY_CAP_FOR_EVERY_LEGAL_T",
        "RESOLVED_CERTIFICATES": resolved,
        "FRONTIER_CERTIFICATES": frontier,
        "RESOLVED_ROW_COUNT": len(resolved),
        "CURSOR_PROFILE_COUNT": len(frontier),
        "TOTAL_T_TERM_COUNT": sum(
            integer(object_row(c)["LEGAL_T_COUNT"]) for c in resolved.values()
        ),
        "FRONTIER_T_TERM_COUNT": sum(
            integer(object_row(c)["LEGAL_T_COUNT"]) for c in frontier.values()
        ),
        "CHANGED_RESOLVED_ROW_COUNT": changed,
        "UNCHANGED_RESOLVED_ROW_COUNT": len(final) - changed,
        "CHANGED_T_TERM_COUNT": sum(
            integer(object_row(c)["CHANGED_T_TERM_COUNT"]) for c in resolved.values()
        ),
        "FINAL_RESOLVED_MAX": final_family["RESOLVED_MAX"],
        "FINAL_RESOLVED_OWNER_IDS": final_family["RESOLVED_OWNER_IDS"],
        "FINAL_FRONTIER_MAX": cursor["BOUND"],
        "FRONTIER_MAXIMIZER_IDS": cursor["MAXIMIZER_IDS"],
        "FRONTIER_MAXIMIZER_COUNT": len(rows(cursor["MAXIMIZER_IDS"])),
        "START_COMPLETE_FAMILY_UB": START_BOUND,
        "FINAL_COMPLETE_FAMILY_UB": final_family["FAMILY_UB"],
        "FINAL_OWNER_IDS": final_family["OWNER_IDS"],
        "REMAINING_GAP": final_family["REMAINING_GAP"],
        "FINAL_FAMILY": final_family,
        "ABOVE_INCUMBENT_PROFILE_IDS": above,
        "ABOVE_INCUMBENT_ROW_COUNT": len(above),
        "INCUMBENT_PROFILE_BOUND": final[integration.STS13_PROFILE].bound,
        "INCUMBENT_SOUNDNESS_STATUS": "PASS",
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_DISJOINT_DIGEST_MATCHED",
        "DOUBLE_COUNT_STATUS": "PASS_MIN_OF_BOUNDS; DISJOINT_PARTITIONS; CURSOR_SLOT_ONLY",
        "WITNESS_SOUNDNESS": soundness,
        "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_77_RECORDED_AND_KNOWN_SUPPORTS",
        "PRESERVED_PREDECESSOR_RESULT": auth.sealed,
        "HISTORICAL_RESULT_BYTES_PRESERVED": True,
        "CURSOR_AUTHORITY_STATUS": "UPDATED_THROUGH_CURSOR_SLOT",
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
        raise AssertionError("tampered complete resolved/cursor executable certificate")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify", action="store_true", help="recompute and verify exact JSON bytes"
    )
    args = parser.parse_args()
    result = compute_result()
    rendered = integration.render(result).encode("utf-8")
    if args.verify:
        if RESULT_PATH.read_bytes() != rendered:
            raise AssertionError("immutable complete result byte replay differs")
    else:
        with RESULT_PATH.open("xb") as out:
            out.write(rendered)
    keys = (
        "FINAL_RESOLVED_MAX",
        "FINAL_FRONTIER_MAX",
        "FINAL_COMPLETE_FAMILY_UB",
        "REMAINING_GAP",
        "TOTAL_T_TERM_COUNT",
    )
    print(
        json.dumps(
            {
                "RESULT_REPLAY_STATUS": "PASS" if args.verify else "CREATED",
                **{k: result[k] for k in keys},
            }
        )
    )


if __name__ == "__main__":
    main()
