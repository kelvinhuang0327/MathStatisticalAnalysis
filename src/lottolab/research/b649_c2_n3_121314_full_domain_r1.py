"""Bounded full-domain N3 adapter for fixed C2 slots (12, 13, 14).

The search stays in the pinned generic kernel. This module rebuilds the kept
17, checks exact integer domain accounting, and decides the task status from
kernel output plus the archived C2 N1/N2 certificates. It does not replace the
kernel and it does not start a second heavy run.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from math import comb
from pathlib import Path
from typing import Any

TASK_ID = "B649_C2_N3_121314_FULL_DOMAIN_R1"
BASE_HEAD = "0ba102858c9d5156b759a172fe0ab0fad01ab8c0"
BASE_TREE = "2a3063313b4bf083590c47c60b18953c55feaa85"
KERNEL_COMMIT = "ed356a09d4abb1040f394b7dc5fbfb913d0c97d4"
C2_RECOUNT_COMMIT = "a2246ced0940ba11441f5eda38eaf67f8b6883e9"
N1_COMMIT = "8087f60aac1a5a06b4ade25feb69cc1f5011f191"
N2_COMMIT = BASE_HEAD

ORDERED_SHA256 = "6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24"
CLASS_ID = "e4b1941183c0583d479c1467d7ce9aadf164190a07734ec592a8cf6f45ee07d7"
REMAINDER_SHA256 = "926ff54c804490e906cd09e620a23d485709f7577ad1470b4b8f866b7c3129e0"
EVALUATOR_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
START_COUNT = 313_263_888
START_COVERAGE_7SET = 44_751_984
DESTROY_SLOTS = (12, 13, 14)
REMOVED_TICKETS = (
    (27, 29, 30, 31, 32, 33),
    (27, 34, 35, 36, 37, 38),
    (27, 39, 40, 41, 42, 43),
)
COUNTING_UNIT = "7_SET"
C49_6 = comb(49, 6)
C49_7 = comb(49, 7)
LEGAL_POOL = C49_6 - 17
FRESH_POOL = LEGAL_POOL - 3
RAW_LEGAL_N3_DOMAIN = comb(LEGAL_POOL, 3)
N1_N2_CLOSED_CANDIDATES = RAW_LEGAL_N3_DOMAIN - comb(FRESH_POOL, 3)
FRESH_CANDIDATES = comb(FRESH_POOL, 3)
PACKET_RAW = 455_747_374_158_108_530_299
PACKET_N1N2 = 293_319_846_830_119
PACKET_FRESH = 455_747_080_838_261_700_180
SOLVER_BUDGET_SECONDS = 3600
CANONICAL_BUDGET_SECONDS = 900
TOTAL_SCIENTIFIC_BUDGET_SECONDS = 4500
MEMORY_BUDGET_BYTES = 2 * 1024 * 1024 * 1024
KERNEL_FILES = (
    "n3.h",
    "n3_bounds.h",
    "n3_checkpoint.c",
    "n3_checkpoint.h",
    "n3_core.c",
    "n3_lower.c",
    "n3_main.c",
    "n3_mtab.c",
    "n3_mtab.h",
    "n3_overlap.c",
    "n3_sig.c",
    "n3_sig.h",
    "n3_solve.c",
    "n3_solve.h",
    "n3_solve_legacy.c",
)

N1_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-k20-c2-exact-n1-neighborhood-r1-result.json"
)
N2_RESULT = (
    "docs/research/matrix-native-results/"
    "b649-k20-c2-orbit-reduced-exact-n2-r1-result.json"
)
EVALUATOR_RELATIVE = "src/lottolab/research/b649_official_any_prize_exact.py"
RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-c2-n3-121314-full-domain-r1-result.json"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def compact_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(value: object) -> str:
    return sha256_bytes(compact_json(value).encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ordered_tickets(root: Path | None = None) -> list[list[int]]:
    document = load_json((root or repo_root()) / N1_RESULT)
    tickets = document["START"]["TICKETS_ORDERED"]
    if sha256_text(tickets) != ORDERED_SHA256:
        raise RuntimeError("C2 ordered portfolio SHA256 mismatch")
    if document["START"]["CANONICAL_CLASS_ID"] != CLASS_ID:
        raise RuntimeError("C2 canonical class id mismatch")
    if document["START"]["CANONICAL_RECOUNT"] != START_COUNT:
        raise RuntimeError("C2 start count mismatch")
    return [list(ticket) for ticket in tickets]


def remainder_tickets(root: Path | None = None) -> list[list[int]]:
    """Drop original zero-based slots 12, 13 and 14. Keep the other 17 in order."""
    tickets = ordered_tickets(root)
    if [tuple(tickets[slot]) for slot in DESTROY_SLOTS] != list(REMOVED_TICKETS):
        raise RuntimeError("removed slots are not the pinned C2 tickets")
    kept = [ticket for index, ticket in enumerate(tickets) if index not in DESTROY_SLOTS]
    if len(kept) != 17 or sha256_text(kept) != REMAINDER_SHA256:
        raise RuntimeError("17-ticket remainder SHA256 mismatch")
    return kept


def domain_integers() -> dict[str, int]:
    if C49_6 != 13_983_816 or LEGAL_POOL != 13_983_799:
        raise RuntimeError("legal pool size mismatch")
    if (
        RAW_LEGAL_N3_DOMAIN != PACKET_RAW
        or N1_N2_CLOSED_CANDIDATES != PACKET_N1N2
        or FRESH_CANDIDATES != PACKET_FRESH
    ):
        raise RuntimeError("packet domain integer mismatch")
    if N1_N2_CLOSED_CANDIDATES + FRESH_CANDIDATES != RAW_LEGAL_N3_DOMAIN:
        raise RuntimeError("domain split does not sum")
    return {
        "C49_6": C49_6,
        "LEGAL_POOL": LEGAL_POOL,
        "FRESH_POOL": FRESH_POOL,
        "RAW_LEGAL_N3_DOMAIN": RAW_LEGAL_N3_DOMAIN,
        "N1_N2_CLOSED_CANDIDATES": N1_N2_CLOSED_CANDIDATES,
        "FRESH_CANDIDATES": FRESH_CANDIDATES,
    }


def canonical_outcome_delta(delta7: int) -> int:
    if isinstance(delta7, bool) or not isinstance(delta7, int):
        raise TypeError("delta7 must be an int")
    return 7 * delta7


def c_ijk_from_residual(usize: int) -> int:
    """7-sets covered by the removed triple and by none of the kept 17."""
    return usize - (C49_7 - START_COVERAGE_7SET)


def marginal_excludes_strict_gain(gx: int, gy: int, gz: int, c_ijk: int) -> bool:
    """sum of marginals <= C_ijk implies delta7 <= 0. Equality is not a strict gain."""
    return gx + gy + gz <= c_ijk


def third_contribution(gz: int, oxz: int, oyz: int, oxyz: int) -> int:
    return gz - oxz - oyz + oxyz


def pair_tail_decision(
    gx: int,
    gy: int,
    oxy: int,
    m: int,
    c_ijk: int,
    remaining_contributions: Sequence[int] | None,
) -> dict[str, Any]:
    """Accept M only when it upper-bounds every remaining legal third ticket.

    A missing tail, or an M below any listed contribution, is not a safe exclusion.
    """
    if remaining_contributions is None:
        return {"safe_exclusion": False, "reason": "INCOMPLETE_TAIL", "bound": None}
    if len(remaining_contributions) == 0:
        return {"safe_exclusion": False, "reason": "EMPTY_TAIL", "bound": None}
    proven_cap = max(remaining_contributions)
    bound = gx + gy - oxy + m
    if m < proven_cap:
        return {
            "safe_exclusion": False,
            "reason": "M_BELOW_PROVEN_CAP",
            "bound": bound,
            "proven_cap": proven_cap,
        }
    return {
        "safe_exclusion": bound <= c_ijk,
        "reason": "PAIR_TAIL" if bound <= c_ijk else "BOUND_ABOVE_C",
        "bound": bound,
        "proven_cap": proven_cap,
    }


def n1_n2_certificate(root: Path | None = None) -> dict[str, Any]:
    """Archived C2 N1 and N2 evidence covers every completion at distance <= 2."""
    base = root or repo_root()
    n1 = load_json(base / N1_RESULT)
    n2 = load_json(base / N2_RESULT)
    accounting = n1["NEIGHBORHOOD_ACCOUNTING"]
    representatives = n2["REPRESENTATIVES"]
    deltas = [row["BEST_DELTA_OUTCOME"] for row in representatives]
    checks = {
        "ordered_sha": n1["START"]["ORDERED_SHA256"] == ORDERED_SHA256
        and n2["START"]["ORDERED_SHA256"] == ORDERED_SHA256,
        "start_count": n1["START"]["CANONICAL_RECOUNT"] == START_COUNT
        and n2["START"]["CANONICAL_RECOUNT"] == START_COUNT,
        "class_id": n1["START"]["CANONICAL_CLASS_ID"] == CLASS_ID
        and n2["START"]["CANONICAL_CLASS_ID"] == CLASS_ID,
        "evaluator": n1["ENGINE_AUTHORITY"]["EVALUATOR_SHA256"] == EVALUATOR_SHA256,
        "n1_universe": accounting["FULLY_ACCOUNTED_CANDIDATES"] == 20 * C49_6,
        "n1_unfinished": accounting["UNFINISHED_CANDIDATES"] == 0,
        "n1_no_strict_gain": accounting["COUNT_STRICTLY_IMPROVING_MOVES"] == 0
        and n1["BEST_IS_GAIN"] is False,
        "n1_unrestricted": accounting["CELL_A_RESTRICTION"].startswith("NONE"),
        "n1_closure": n1["N1_LOCAL_CLOSURE_STATUS"].startswith("C2_N1_LOCAL_CLOSURE_PROVEN"),
        "n2_pairs": n2["MATHEMATICALLY_COVERED_ORIGINAL_PAIRS"] == 190
        and n2["ORBIT_REDUCTION"]["RAW_SLOT_PAIRS"] == 190,
        "n2_representatives": len(representatives) == 94
        and n2["ORBIT_REDUCTION"]["REPRESENTATIVES"] == 94,
        "n2_pending_empty": n2["PENDING_REPRESENTATIVES_ENGINE"] == [],
        "n2_no_strict_gain": deltas == [0] * len(deltas)
        and n2["BEST_IS_GAIN"] is False
        and n2["BEST_DELTA"] == 0,
        "n2_closure": n2["N2_LOCAL_CLOSURE_STATUS"].startswith("C2_N2_LOCAL_CLOSURE_PROVEN"),
        "n2_symmetry": "fixing the START" in n2["ORBIT_REDUCTION"]["COVERAGE_ARGUMENT"],
    }
    return {
        "applies": all(checks.values()),
        "checks": checks,
        "closed_candidates": N1_N2_CLOSED_CANDIDATES if all(checks.values()) else 0,
        "argument": (
            "A legal completion that reuses at least one original removed ticket "
            "differs from C2 in 0, 1, or 2 tickets. N1 closed every single-ticket "
            "replacement over C(49,6). N2 closed every two-ticket replacement of "
            "the 190 slot pairs. Neither found a strict gain."
        ),
    }


def delta7_of(
    gx: int, gy: int, gz: int, oxy: int, oxz: int, oyz: int, oxyz: int, c_ijk: int
) -> int:
    return gx + gy + gz - oxy - oxz - oyz + oxyz - c_ijk


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def _triple_key(ids: Sequence[str]) -> tuple[str, str, str]:
    ordered = tuple(sorted(ids))
    if len(ordered) != 3:
        raise ValueError("triple key needs 3 ids")
    return ordered  # type: ignore[return-value]


def classify_toy_domain(
    tickets: Sequence[Mapping[str, Any]],
    c_ijk: int,
    pair_overlap: Mapping[tuple[str, str], int],
    triple_overlap: Mapping[tuple[str, str, str], int],
    *,
    exact_budget: int | None = None,
    reuse_certified: bool = True,
) -> dict[str, Any]:
    """Classify every unordered triple in a tiny explicit universe.

    Pair-tail M for a pair is the max third-contribution over every other ticket
    in this same universe. That list is complete, so the bound is admissible.
    """
    ids = [str(ticket["id"]) for ticket in tickets]
    if len(ids) != len(set(ids)):
        raise ValueError("toy ticket ids must be unique")
    by_id = {str(ticket["id"]): ticket for ticket in tickets}
    removed = {ticket_id for ticket_id, ticket in by_id.items() if ticket["original_removed"]}
    buckets = {
        "N1_N2_CERTIFIED_NO_GAIN": 0,
        "EXACT_EVALUATED": 0,
        "PROVEN_BOUND_PRUNED": 0,
        "UNRESOLVED_FRONTIER": 0,
    }
    certificates: list[dict[str, Any]] = []
    best_delta7 = None
    exact_used = 0
    positive: list[tuple[str, str, str]] = []
    total = comb(len(ids), 3)
    for i, a in enumerate(ids):
        for j in range(i + 1, len(ids)):
            b = ids[j]
            for k in range(j + 1, len(ids)):
                c = ids[k]
                triple = (a, b, c)
                if removed.intersection(triple):
                    if reuse_certified:
                        buckets["N1_N2_CERTIFIED_NO_GAIN"] += 1
                        continue
                    buckets["UNRESOLVED_FRONTIER"] += 1
                    continue
                rs = [int(by_id[name]["r"]) for name in triple]
                if marginal_excludes_strict_gain(rs[0], rs[1], rs[2], c_ijk):
                    buckets["PROVEN_BOUND_PRUNED"] += 1
                    certificates.append(
                        {
                            "kind": "MARGINAL",
                            "triple": list(triple),
                            "inequality": "gX+gY+gZ<=C_ijk",
                            "bound": sum(rs),
                            "count": 1,
                        }
                    )
                    continue
                pruned = False
                for pair in ((a, b, c), (a, c, b), (b, c, a)):
                    x, y, _z = pair
                    oxy = int(pair_overlap[_pair_key(x, y)])
                    contributions = []
                    for other in ids:
                        if other in (x, y) or other in removed:
                            continue
                        oxz = int(pair_overlap[_pair_key(x, other)])
                        oyz = int(pair_overlap[_pair_key(y, other)])
                        oxyz = int(triple_overlap[_triple_key((x, y, other))])
                        contributions.append(
                            third_contribution(int(by_id[other]["r"]), oxz, oyz, oxyz)
                        )
                    m = max(contributions) if contributions else 0
                    decision = pair_tail_decision(
                        int(by_id[x]["r"]),
                        int(by_id[y]["r"]),
                        oxy,
                        m,
                        c_ijk,
                        contributions if contributions else None,
                    )
                    if decision["safe_exclusion"]:
                        buckets["PROVEN_BOUND_PRUNED"] += 1
                        certificates.append(
                            {
                                "kind": "PAIR_TAIL",
                                "pair": [x, y],
                                "inequality": "gX+gY-OXY+M<=C_ijk",
                                "bound": decision["bound"],
                                "M": m,
                                "count": 1,
                            }
                        )
                        pruned = True
                        break
                if pruned:
                    continue
                if exact_budget is not None and exact_used >= exact_budget:
                    buckets["UNRESOLVED_FRONTIER"] += 1
                    continue
                oxy = int(pair_overlap[_pair_key(a, b)])
                oxz = int(pair_overlap[_pair_key(a, c)])
                oyz = int(pair_overlap[_pair_key(b, c)])
                oxyz = int(triple_overlap[_triple_key(triple)])
                delta7 = delta7_of(rs[0], rs[1], rs[2], oxy, oxz, oyz, oxyz, c_ijk)
                exact_used += 1
                buckets["EXACT_EVALUATED"] += 1
                if best_delta7 is None or delta7 > best_delta7:
                    best_delta7 = delta7
                if delta7 > 0:
                    positive.append(triple)
    if sum(buckets.values()) != total:
        raise RuntimeError("toy accounting is not a partition")
    status = status_from_accounting(
        buckets,
        stop_reason="CLOSED" if buckets["UNRESOLVED_FRONTIER"] == 0 else "TIME_LIMIT",
        verified_gain=False,
        positive_exact=bool(positive),
    )
    return {
        "buckets": buckets,
        "total": total,
        "best_delta7": best_delta7,
        "positive": [list(item) for item in positive],
        "certificates": certificates,
        "status_if_no_recount": status,
    }


def status_from_accounting(
    buckets: Mapping[str, int],
    *,
    stop_reason: str,
    verified_gain: bool,
    positive_exact: bool = False,
) -> str:
    if verified_gain:
        return "VERIFIED_STRICT_GAIN"
    unresolved = int(buckets["UNRESOLVED_FRONTIER"])
    if unresolved != 0 or stop_reason != "CLOSED" or positive_exact:
        return "INCOMPLETE_FRONTIER_OPEN"
    if int(buckets["EXACT_EVALUATED"]) < 0 or int(buckets["PROVEN_BOUND_PRUNED"]) < 0:
        return "INCOMPLETE_FRONTIER_OPEN"
    return "EXHAUSTIVE_NO_GAIN_CLOSED"


def fresh_marginal_pruned(
    *,
    prefix_l: int,
    rmin: int,
    rho: int,
    f0: int,
    removed_r: Sequence[int],
) -> int | None:
    """Count fresh triples whose marginal sum is strictly below F0.

    Returns None when the kernel thresholds do not match the proved inequality.
    """
    if rmin != max(0, f0 - 2 * rho):
        return None
    if any(value < 0 for value in removed_r) or rho < 0 or f0 < 0:
        return None
    outside = C49_6 - prefix_l
    if outside < 0 or prefix_l < 0:
        return None
    if f0 < 2 * rho and outside > 0:
        return None
    kept_outside = 17 if rmin > 0 else 0
    originals_outside = sum(1 for value in removed_r if value < rmin)
    fresh_outside = outside - kept_outside - originals_outside
    if fresh_outside < 0 or fresh_outside > FRESH_POOL:
        return None
    inside = FRESH_POOL - fresh_outside
    return FRESH_CANDIDATES - comb(inside, 3)


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise TypeError("expected an integer field")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected an integer field, got {type(value).__name__}")


def normalize_kernel_document(document: Mapping[str, Any]) -> dict[str, Any]:
    solver = document.get("SOLVER") or {}
    incumbent = document["INCUMBENT"]
    stats = document["R_STATS"]
    ran = bool(solver.get("RAN"))
    ties = solver.get("TIES") or []
    return {
        "ran": ran,
        "closed": bool(solver.get("CLOSED")) if ran else False,
        "stop_reason": str(solver.get("STOP_REASON") or "NO_SOLVER"),
        "improved": bool(solver.get("IMPROVED")) if ran else False,
        "f0": _as_int(incumbent["F0_DIRECT"]),
        "f0_ie": _as_int(incumbent["F0_INCLUSION_EXCLUSION"]),
        "best_f": _as_int(solver["BEST_F"]) if ran else _as_int(incumbent["F0_DIRECT"]),
        "rho": _as_int(stats["MAX"]),
        "rmin": _as_int(solver["RMIN"]) if ran else None,
        "prefix_l": _as_int(solver["CANDIDATE_PREFIX_L"]) if ran else None,
        "removed_r": [_as_int(value) for value in incumbent["REMOVED_R"]],
        "usize": _as_int(document["RESIDUAL_SUBSETS"]),
        "identities_ok": bool(document["IDENTITIES"]["PASS"]),
        "accounted": _as_int(solver["TRIPLES_ACCOUNTED"]) if ran else None,
        "total": _as_int(solver["TRIPLES_TOTAL"]) if ran else None,
        "open_upper_bound": _as_int(solver["OPEN_UPPER_BOUND"]) if ran else None,
        "tie_count": _as_int(solver.get("OPTIMAL_TRIPLE_COUNT", 0)) if ran else 0,
        "ties_stored": (
            _as_int(solver["TIES_STORED"])
            if ran and "TIES_STORED" in solver
            else (len(ties) if ran else 0)
        ),
        "ties": ties if ran else [],
        "a_last": _as_int(solver["A_LAST"]) if ran and "A_LAST" in solver else None,
        "prune_audit_failures": _as_int(solver.get("PRUNE_AUDIT_FAILURES", 0)) if ran else 0,
        "leaf_audit_failures": _as_int(solver.get("LEAF_DIRECT_AUDIT_FAILURES", 0)) if ran else 0,
        "seconds": solver.get("SECONDS") if ran else None,
    }


def _ticket_key(ticket: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(int(number) for number in ticket))


def account_kernel(
    summary: Mapping[str, Any] | None,
    *,
    certificate_ok: bool,
    kept: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Partition the legal domain. Unnamed kernel leaves stay unresolved."""
    kept_keys = {_ticket_key(ticket) for ticket in kept}
    removed_keys = {_ticket_key(ticket) for ticket in REMOVED_TICKETS}
    n1n2 = N1_N2_CLOSED_CANDIDATES if certificate_ok else 0
    fresh_pruned = 0
    fresh_exact = 0
    certificates: list[dict[str, Any]] = []
    contradiction = False
    listed_gain: list[list[int]] | None = None
    stop_reason = "NO_KERNEL_RESULT"
    open_upper = None
    first_frontier = "entire fresh domain; kernel result absent"
    marginal = None
    if certificate_ok:
        certificates.append(
            {
                "kind": "N1_N2_REUSE",
                "inequality": "distance<=2 from C2 and archived N1/N2 best delta is 0",
                "bound": 0,
                "count": str(n1n2),
            }
        )
    if summary is not None:
        stop_reason = str(summary["stop_reason"])
        open_upper = summary["open_upper_bound"]
        f0_ok = (
            summary["identities_ok"]
            and summary["f0"] == summary["f0_ie"]
            and summary["f0"] == c_ijk_from_residual(int(summary["usize"]))
            and summary["prune_audit_failures"] == 0
            and summary["leaf_audit_failures"] == 0
        )
        if (
            f0_ok
            and summary["ran"]
            and summary["rmin"] is not None
            and summary["prefix_l"] is not None
        ):
            marginal = fresh_marginal_pruned(
                prefix_l=int(summary["prefix_l"]),
                rmin=int(summary["rmin"]),
                rho=int(summary["rho"]),
                f0=int(summary["f0"]),
                removed_r=summary["removed_r"],
            )
        superset_closed = (
            f0_ok
            and summary["ran"]
            and summary["closed"]
            and summary["accounted"] == summary["total"] == comb(C49_6, 3)
            and not summary["improved"]
            and int(summary["best_f"]) <= int(summary["f0"])
        )
        if superset_closed:
            fresh_pruned = FRESH_CANDIDATES
            marginal = FRESH_CANDIDATES
            stop_reason = "CLOSED"
            certificates.append(
                {
                    "kind": "KERNEL_SUPERSET_CLOSURE",
                    "inequality": (
                        "F<=F0=C_ijk for every triple in C(C(49,6),3), hence for every fresh triple"
                    ),
                    "bound": int(summary["f0"]),
                    "count": str(FRESH_CANDIDATES),
                }
            )
            first_frontier = None
        elif marginal:
            fresh_pruned = marginal
            certificates.append(
                {
                    "kind": "MARGINAL",
                    "inequality": (
                        "gX+gY+gZ<=rmin-1+2*rho<F0=C_ijk for every fresh triple with one r<rmin"
                    ),
                    "bound": int(summary["f0"]),
                    "count": str(marginal),
                }
            )
        if summary["improved"] and summary["ties"]:
            for triple in summary["ties"]:
                keys = [_ticket_key(ticket) for ticket in triple]
                if len(set(keys)) != 3 or any(len(key) != 6 for key in keys):
                    continue
                if any(key in kept_keys for key in keys):
                    continue
                listed_gain = [list(map(int, ticket)) for ticket in triple]
                if any(key in removed_keys for key in keys):
                    contradiction = True
                break
        if contradiction:
            n1n2 = 0
            certificates = [row for row in certificates if row["kind"] != "N1_N2_REUSE"]
        if listed_gain is not None:
            # A stored strict gain is one exact candidate. Unstored ties stay unresolved.
            # It cannot also sit in a marginal band that proves F < F0.
            if not contradiction and marginal == FRESH_CANDIDATES:
                marginal = None
                fresh_pruned = 0
                certificates = [row for row in certificates if row["kind"] != "MARGINAL"]
            fresh_exact = 1
        if not superset_closed:
            inside = FRESH_CANDIDATES - (marginal or 0)
            first_frontier = (
                f"fresh triples inside the r>=rmin prefix; count={inside - fresh_exact}; "
                f"kernel_stop={stop_reason}; kernel_anchor={summary.get('a_last')}; "
                f"open_upper_bound_F={open_upper}"
            )
    unresolved = RAW_LEGAL_N3_DOMAIN - n1n2 - fresh_pruned - fresh_exact
    buckets = {
        "N1_N2_CERTIFIED_NO_GAIN": n1n2,
        "EXACT_EVALUATED": fresh_exact,
        "PROVEN_BOUND_PRUNED": fresh_pruned,
        "UNRESOLVED_FRONTIER": unresolved,
    }
    if sum(buckets.values()) != RAW_LEGAL_N3_DOMAIN or unresolved < 0:
        raise RuntimeError("legal-domain accounting failed")
    return {
        "buckets": buckets,
        "certificates": certificates,
        "stop_reason": stop_reason,
        "open_upper_bound": open_upper,
        "first_unfinished_frontier": first_frontier,
        "listed_gain": listed_gain,
        "n1n2_contradiction": contradiction,
        "marginal_pruned": marginal,
    }


def decision_from_recount(
    *,
    count: int,
    delta7: int,
    structural_ok: bool,
    evaluator_sha256: str,
) -> bool:
    if evaluator_sha256 != EVALUATOR_SHA256 or not structural_ok or delta7 <= 0:
        return False
    delta = count - START_COUNT
    return count > START_COUNT and delta == canonical_outcome_delta(delta7)


def portfolio_structure_ok(
    portfolio: Sequence[Sequence[int]],
    kept: Sequence[Sequence[int]],
    new_tickets: Sequence[Sequence[int]],
) -> bool:
    if len(portfolio) != 20 or len(kept) != 17 or len(new_tickets) != 3:
        return False
    kept_keys = [_ticket_key(ticket) for ticket in kept]
    new_keys = [_ticket_key(ticket) for ticket in new_tickets]
    if len(set(kept_keys)) != 17 or len(set(new_keys)) != 3:
        return False
    if set(kept_keys).intersection(new_keys):
        return False
    expected: list[tuple[int, ...]] = []
    new_iter = iter(new_keys)
    kept_iter = iter(kept_keys)
    for index in range(20):
        expected.append(next(new_iter) if index in DESTROY_SLOTS else next(kept_iter))
    portfolio_keys = [_ticket_key(ticket) for ticket in portfolio]
    if portfolio_keys != expected:
        return False
    return all(
        len(key) == 6 and len(set(key)) == 6 and all(1 <= number <= 49 for number in key)
        for key in portfolio_keys
    )


def recount_pinned(portfolio: Sequence[Sequence[int]], root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    path = base / EVALUATOR_RELATIVE
    digest = sha256_bytes(path.read_bytes())
    if digest != EVALUATOR_SHA256:
        raise RuntimeError("canonical evaluator SHA256 mismatch")
    from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

    outcome = evaluate_portfolio([tuple(ticket) for ticket in portfolio])
    return {
        "count": int(outcome.official_any_prize_outcome_count),
        "evaluator_sha256": digest,
        "evaluator_path": EVALUATOR_RELATIVE,
    }


def accept_verified_gain(
    portfolio: Sequence[Sequence[int]],
    kept: Sequence[Sequence[int]],
    new_tickets: Sequence[Sequence[int]],
    delta7: int,
    root: Path | None = None,
) -> dict[str, Any]:
    structural_ok = portfolio_structure_ok(portfolio, kept, new_tickets)
    if not structural_ok:
        return {"accepted": False, "reason": "ILLEGAL_PORTFOLIO", "recount": None}
    recount = recount_pinned(portfolio, root)
    accepted = decision_from_recount(
        count=recount["count"],
        delta7=delta7,
        structural_ok=True,
        evaluator_sha256=recount["evaluator_sha256"],
    )
    return {
        "accepted": accepted,
        "reason": "PASS" if accepted else "RECOUNT_NOT_STRICT_GAIN",
        "recount": recount,
        "canonical_delta": recount["count"] - START_COUNT,
        "claimed_canonical_delta": canonical_outcome_delta(delta7),
    }


def fixed_toy() -> dict[str, Any]:
    tickets = (
        {"id": "a", "r": 5, "original_removed": True},
        {"id": "b", "r": 4, "original_removed": True},
        {"id": "c", "r": 4, "original_removed": True},
        {"id": "d", "r": 3, "original_removed": False},
        {"id": "e", "r": 3, "original_removed": False},
        {"id": "f", "r": 2, "original_removed": False},
        {"id": "g", "r": 1, "original_removed": False},
    )
    zeros = {}
    ids = [ticket["id"] for ticket in tickets]
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            zeros[(left, right)] = 0
    triples = {}
    for i, a in enumerate(ids):
        for j in range(i + 1, len(ids)):
            for k in range(j + 1, len(ids)):
                triples[(a, ids[j], ids[k])] = 0
    return classify_toy_domain(tickets, 6, zeros, triples)


def launch_report(root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    kept = remainder_tickets(base)
    domain = domain_integers()
    certificate = n1_n2_certificate(base)
    toy = fixed_toy()
    return {
        "TASK_ID": TASK_ID,
        "COUNTING_UNIT": COUNTING_UNIT,
        "START_ORDERED_SHA": ORDERED_SHA256,
        "START_CLASS_ID": CLASS_ID,
        "START_CANONICAL_COUNT": START_COUNT,
        "REMAINDER_SHA256": sha256_text(kept),
        "REMOVED_TICKETS": [list(ticket) for ticket in REMOVED_TICKETS],
        "NUMBER_27_IN_REMAINDER": any(27 in ticket for ticket in kept),
        "DOMAIN": domain,
        "N1_N2_CERTIFICATE_APPLIES": certificate["applies"],
        "CANONICAL_DELTA_OF_3": canonical_outcome_delta(3),
        "TOY_BUCKETS": toy["buckets"],
        "TOY_BEST_DELTA7": toy["best_delta7"],
        "TOY_STATUS_IF_NO_RECOUNT": toy["status_if_no_recount"],
        "SOLVER": "NOT_THIS_ENTRY",
    }


def kernel_interface_accepts_kept_removed(source: str) -> bool:
    return '--kept' in source and '--removed' in source and "need 3 removed tickets" in source


def memory_limit_capability() -> dict[str, Any]:
    """Record whether the OS can hard-cap this process near 2 GiB.

    On this macOS, setrlimit of RLIMIT_AS, RLIMIT_DATA and RLIMIT_RSS returns
    EINVAL. The solver driver therefore uses an RSS monitor stop-loss. That
    monitor is not an OS hard cap.
    """
    results = {}
    for name in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
        kind = getattr(resource, name)
        before = resource.getrlimit(kind)
        enforced = False
        error = None
        try:
            resource.setrlimit(kind, (MEMORY_BUDGET_BYTES, before[1]))
            enforced = True
            resource.setrlimit(kind, before)
        except (ValueError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        results[name] = {"before": list(before), "set_soft_2gib": enforced, "error": error}
    os_hard = any(row["set_soft_2gib"] for row in results.values())
    return {
        "OS_HARD_LIMIT_AVAILABLE": os_hard,
        "OS_HARD_LIMIT_BYTES": MEMORY_BUDGET_BYTES if os_hard else None,
        "MONITOR_STOP_LOSS_BYTES": MEMORY_BUDGET_BYTES,
        "MONITOR_IS_OS_HARD_CAP": False,
        "RLIMITS": results,
    }


def heavy_slot_blocked(process_lines: Sequence[str], lock_held: bool) -> bool:
    if lock_held:
        return True
    own = str(os.getpid())
    for raw in process_lines:
        line = raw.strip()
        if not line:
            continue
        pid, _, command = line.partition(" ")
        if pid == own or not command:
            continue
        executable = command.split()[0].rsplit("/", 1)[-1]
        if executable == "n3-exact" or executable.startswith("n3-exact"):
            return True
        if (
            "python" in executable
            and "b649_c2_n3_121314_full_domain_r1" in command
            and command.rstrip().endswith(" solve")
        ):
            return True
    return False


def _process_lines() -> list[str]:
    probe = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.stdout.splitlines()


def _lock_held(path: Path) -> bool:
    if not path.exists():
        return False
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def preflight(root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    failures: list[str] = []
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=base, text=True).strip()
    if head != BASE_HEAD:
        failures.append(f"HEAD {head} is not pinned base {BASE_HEAD}")
    if tree != BASE_TREE:
        failures.append(f"tree {tree} is not pinned base tree {BASE_TREE}")
    try:
        kept = remainder_tickets(base)
    except RuntimeError as exc:
        failures.append(str(exc))
        kept = []
    evaluator = sha256_bytes((base / EVALUATOR_RELATIVE).read_bytes())
    if evaluator != EVALUATOR_SHA256:
        failures.append("evaluator SHA256 mismatch")
    source = subprocess.check_output(
        ["git", "show", f"{KERNEL_COMMIT}:src/lottolab/research/b649_n3_exact/n3_main.c"],
        cwd=base,
        text=True,
    )
    if not kernel_interface_accepts_kept_removed(source):
        failures.append("pinned kernel does not accept --kept/--removed")
    certificate = n1_n2_certificate(base)
    if not certificate["applies"]:
        failures.append("N1/N2 certificate does not apply to this C2")
    run_dir = base / ".task-data" / TASK_ID / "run1"
    lock_path = run_dir / "writer.lock"
    blocked = heavy_slot_blocked(_process_lines(), _lock_held(lock_path))
    if blocked:
        failures.append("heavy scientific slot is already held")
    memory = memory_limit_capability()
    return {
        "ok": not failures,
        "failures": failures,
        "HEAD": head,
        "TREE": tree,
        "REMAINDER_SHA256": sha256_text(kept) if kept else None,
        "EVALUATOR_SHA256": evaluator,
        "KERNEL_COMMIT": KERNEL_COMMIT,
        "KERNEL_INTERFACE": not any("kernel" in item for item in failures),
        "N1_N2_CERTIFICATE_APPLIES": certificate["applies"],
        "HEAVY_SLOT_HELD": blocked,
        "MEMORY": memory,
        "NUMBER_27_SUPPORT_IN_REMAINDER": sum(ticket.count(27) for ticket in kept),
    }


def _kernel_source_digest(source_dir: Path) -> tuple[str, dict[str, str]]:
    hashes = {name: sha256_bytes((source_dir / name).read_bytes()) for name in KERNEL_FILES}
    digest = sha256_bytes(compact_json(hashes).encode("utf-8"))
    return digest, hashes


def _extract_kernel(root: Path, source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    for name in KERNEL_FILES:
        blob = subprocess.check_output(
            ["git", "show", f"{KERNEL_COMMIT}:src/lottolab/research/b649_n3_exact/{name}"],
            cwd=root,
        )
        (source_dir / name).write_bytes(blob)


def _sample_rss(pid: int) -> int | None:
    probe = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    text = probe.stdout.strip()
    if not text:
        return None
    return int(text.split()[0]) * 1024


def _release(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def run_solver_once(root: Path | None = None) -> dict[str, Any]:
    """One scientific execution. A second call refuses without launching."""
    base = root or repo_root()
    report = preflight(base)
    result_path = base / RESULT_RELATIVE
    if not report["ok"]:
        payload = _result_payload(
            status="BLOCKED_PRELAUNCH",
            preflight=report,
            accounting=None,
            extra={"STOP_REASON": "PREFLIGHT", "SOLVER_LAUNCHED": False},
        )
        _write_json(result_path, payload)
        return payload
    run_dir = base / ".task-data" / TASK_ID / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    started = run_dir / "SOLVER_STARTED"
    if started.exists():
        if result_path.exists():
            return load_json(result_path)
        raise RuntimeError("solver marker exists and no result was written; not restarting")
    lock_fd = os.open(run_dir / "writer.lock", os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        payload = _result_payload(
            status="BLOCKED_PRELAUNCH",
            preflight=report,
            accounting=None,
            extra={"STOP_REASON": "LOCK_HELD", "SOLVER_LAUNCHED": False},
        )
        _write_json(result_path, payload)
        return payload
    try:
        return _execute_solver(base, run_dir, report, result_path, started)
    finally:
        _release(lock_fd)


def _load_kernel_document(path: Path, truncate_after: int = 32_000_000) -> dict[str, Any]:
    """Load solver JSON. A huge TIES array is truncated to its first triple.

    OPTIMAL_TRIPLE_COUNT and TIES_STORED stay as the kernel wrote them, so the
    unnamed tail is not treated as enumerated.
    """
    raw = path.read_bytes()
    marker = b'"TIES":['
    if len(raw) > truncate_after and marker in raw:
        start = raw.find(marker)
        body = start + len(marker)
        anchor = b'],"ANCHORS_COMPLETED"'
        anchor_at = raw.find(anchor, start)
        if raw[body:body + 1] == b"[" and anchor_at > body:
            depth = 0
            end = body
            for index in range(body, anchor_at):
                char = raw[index:index + 1]
                if char == b"[":
                    depth += 1
                elif char == b"]":
                    depth -= 1
                    if depth == 0:
                        end = index + 1
                        break
            raw = raw[:end] + b"]" + raw[anchor_at + 1:]
    return json.loads(raw)


def _execute_solver(
    base: Path,
    run_dir: Path,
    report: dict[str, Any],
    result_path: Path,
    started: Path,
) -> dict[str, Any]:
    source_dir = run_dir / "kernel-src"
    _extract_kernel(base, source_dir)
    source_sha, source_files = _kernel_source_digest(source_dir)
    binary = run_dir / "n3-exact"
    sources = [str(source_dir / name) for name in KERNEL_FILES if name.endswith(".c")]
    compile_argv = [
        "clang",
        "-std=c11",
        "-O3",
        "-Wall",
        "-Wextra",
        f'-DN3_ENGINE_SHA256="{source_sha}"',
        *sources,
        "-o",
        str(binary),
    ]
    subprocess.run(compile_argv, check=True, cwd=base)
    binary_sha = sha256_bytes(binary.read_bytes())
    fd = os.open(started, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.close(fd)
    kept = remainder_tickets(base)
    removed = [list(ticket) for ticket in REMOVED_TICKETS]
    out_path = run_dir / "kernel-result.json"
    checkpoint = run_dir / "solver.anchors.jsonl"
    argv = [
        str(binary),
        "--kept",
        _tickets_arg(kept),
        "--removed",
        _tickets_arg(removed),
        "--out",
        str(out_path),
        "--checkpoint",
        str(checkpoint),
        "--time-limit",
        str(SOLVER_BUDGET_SECONDS),
    ]
    log_path = run_dir / "solver.log"
    scientific_started = time.monotonic()
    peak_rss = 0
    stop_reason = "KERNEL_EXIT"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(argv, cwd=base, stdout=log, stderr=log)
        while process.poll() is None:
            elapsed = time.monotonic() - scientific_started
            rss = _sample_rss(process.pid)
            if rss is not None:
                peak_rss = max(peak_rss, rss)
            if rss is not None and rss > MEMORY_BUDGET_BYTES:
                stop_reason = "MEMORY_MONITOR_STOP_LOSS"
                process.send_signal(signal.SIGTERM)
                break
            if elapsed > SOLVER_BUDGET_SECONDS + 150:
                stop_reason = "PARENT_WALL_STOP_LOSS"
                process.send_signal(signal.SIGTERM)
                break
            time.sleep(2)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
            stop_reason = "PARENT_WALL_STOP_LOSS"
    process_wall = time.monotonic() - scientific_started
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    kernel_doc = _load_kernel_document(out_path) if out_path.exists() else None
    summary = normalize_kernel_document(kernel_doc) if kernel_doc else None
    timing = None if kernel_doc is None else kernel_doc.get("TIMING") or {}
    kernel_timing_total = None if kernel_doc is None else timing.get("TOTAL")
    kernel_peak = None if kernel_doc is None else kernel_doc.get("PEAK_RSS_BYTES")
    # TIMING.TOTAL ends when the search returns, before the JSON write.
    # The write and the recount are archival work inside the canonical budget.
    if isinstance(kernel_timing_total, (int, float)) and not isinstance(kernel_timing_total, bool):
        solver_wall = float(kernel_timing_total)
        archive_gap = max(0.0, process_wall - solver_wall)
    else:
        solver_wall = process_wall
        archive_gap = 0.0
    certificate = n1_n2_certificate(base)
    accounting = account_kernel(summary, certificate_ok=certificate["applies"], kept=kept)
    verified = False
    recount: dict[str, Any] | None = None
    canonical_started = time.monotonic()
    if accounting["listed_gain"] is not None and summary is not None:
        delta7 = int(summary["best_f"]) - int(summary["f0"])
        ordered_gain = sorted(accounting["listed_gain"], key=_ticket_key)
        portfolio = _replace_slots(kept, ordered_gain)
        recount = accept_verified_gain(portfolio, kept, ordered_gain, delta7, base)
        verified = bool(recount["accepted"])
    canonical_wall = archive_gap + (time.monotonic() - canonical_started)
    if solver_wall + canonical_wall > TOTAL_SCIENTIFIC_BUDGET_SECONDS:
        stop_reason = "TOTAL_BUDGET"
    kernel_stop = accounting["stop_reason"] if stop_reason == "KERNEL_EXIT" else stop_reason
    if kernel_stop == "CLOSED" and stop_reason != "KERNEL_EXIT":
        kernel_stop = stop_reason
    status = status_from_accounting(
        accounting["buckets"],
        stop_reason=kernel_stop,
        verified_gain=verified,
        positive_exact=accounting["listed_gain"] is not None and not verified,
    )
    if status == "EXHAUSTIVE_NO_GAIN_CLOSED" and stop_reason != "KERNEL_EXIT":
        status = "INCOMPLETE_FRONTIER_OPEN"
    payload = _result_payload(
        status=status,
        preflight=report,
        accounting=accounting,
        extra={
            "SOLVER_LAUNCHED": True,
            "STOP_REASON": stop_reason if kernel_doc is None else accounting["stop_reason"],
            "PARENT_STOP_REASON": stop_reason,
            "SOLVER_WALL_SECONDS": solver_wall,
            "PROCESS_WALL_SECONDS": process_wall,
            "CANONICAL_VERIFICATION_WALL_SECONDS": canonical_wall,
            "PEAK_RSS_BYTES_SAMPLED": peak_rss,
            "KERNEL_PEAK_RSS_BYTES": kernel_peak,
            "RU_MAXRSS_RAW": usage.ru_maxrss,
            "RU_MAXRSS_UNIT": "BYTES_ON_MACOS",
            "N3_KERNEL_SOURCE_SHA256": source_sha,
            "N3_KERNEL_SOURCE_FILES": source_files,
            "N3_KERNEL_BINARY_SHA256": binary_sha,
            "N3_KERNEL_COMMIT": KERNEL_COMMIT,
            "KERNEL_ARGV": argv,
            "CHECKPOINT_LOCATOR": str(checkpoint),
            "KERNEL_RESULT_LOCATOR": str(out_path),
            "KERNEL_RESULT_SHA256": (
                sha256_bytes(out_path.read_bytes()) if out_path.exists() else None
            ),
            "CANONICAL_GAIN_RECOUNT": (
                "PASS" if verified else ("FAIL" if recount else "NOT_APPLICABLE")
            ),
            "RECOUNT": recount,
            "LISTED_GAIN": accounting["listed_gain"],
            "MEMORY_LIMIT": report["MEMORY"],
            "BEST_DELTA_7SET": (
                None if summary is None else int(summary["best_f"]) - int(summary["f0"])
            ),
            "BEST_F": None if summary is None else summary["best_f"],
            "F0": None if summary is None else summary["f0"],
        },
    )
    _write_json(result_path, payload)
    _write_json(run_dir / "task-result.json", payload)
    return payload


def _tickets_arg(tickets: Sequence[Sequence[int]]) -> str:
    return ";".join(",".join(str(number) for number in ticket) for ticket in tickets)


def _replace_slots(
    kept: Sequence[Sequence[int]], new_tickets: Sequence[Sequence[int]]
) -> list[list[int]]:
    portfolio: list[list[int]] = []
    kept_iter = iter(kept)
    new_iter = iter(new_tickets)
    for index in range(20):
        portfolio.append(list(next(new_iter) if index in DESTROY_SLOTS else next(kept_iter)))
    return portfolio


def _result_payload(
    *,
    status: str,
    preflight: Mapping[str, Any],
    accounting: Mapping[str, Any] | None,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    buckets = None if accounting is None else accounting["buckets"]
    payload: dict[str, Any] = {
        "SCHEMA": "B649_C2_N3_121314_FULL_DOMAIN_R1",
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "COUNTING_UNIT": COUNTING_UNIT,
        "START_ORDERED_SHA": ORDERED_SHA256,
        "START_CLASS_ID": CLASS_ID,
        "START_CANONICAL_COUNT": START_COUNT,
        "DESTROY_SLOTS": list(DESTROY_SLOTS),
        "REMOVED_TICKETS": [list(ticket) for ticket in REMOVED_TICKETS],
        "REMAINDER_SHA256": REMAINDER_SHA256,
        "EVALUATOR_SHA256": EVALUATOR_SHA256,
        "RAW_LEGAL_N3_DOMAIN": str(RAW_LEGAL_N3_DOMAIN),
        "N1_N2_CLOSED_CANDIDATES": (
            None if buckets is None else str(buckets["N1_N2_CERTIFIED_NO_GAIN"])
        ),
        "EXACT_EVALUATED_CANDIDATES": None if buckets is None else str(buckets["EXACT_EVALUATED"]),
        "BOUND_PRUNED_CANDIDATES": None if buckets is None else str(buckets["PROVEN_BOUND_PRUNED"]),
        "UNRESOLVED_FRONTIER_CANDIDATES": (
            None if buckets is None else str(buckets["UNRESOLVED_FRONTIER"])
        ),
        "ACCOUNTING_SUM": None if buckets is None else str(sum(buckets.values())),
        "SAFE_PRUNING_CERTIFICATES": None if accounting is None else accounting["certificates"],
        "FIRST_UNFINISHED_FRONTIER": (
            None if accounting is None else accounting["first_unfinished_frontier"]
        ),
        "OPEN_UPPER_BOUND": None if accounting is None else accounting["open_upper_bound"],
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "PR": "NOT_CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "PREFLIGHT": preflight,
        "ACCOUNTING_NOTE": (
            None
            if buckets is None
            else (
                "Buckets partition legal 3-ticket completions. "
                "Kernel-internal exact leaves that the output does not identify "
                "stay in UNRESOLVED_FRONTIER."
            )
        ),
    }
    payload.update(dict(extra))
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("report", "solve"), default="report")
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run_solver_once() if args.command == "solve" else launch_report()
    print(compact_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
