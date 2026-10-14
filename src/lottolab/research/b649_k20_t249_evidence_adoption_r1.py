"""Local adoption of the Fresh-context accepted T249 bound for one profile.

E=93, W=827, T+I=293, Core=14, Zero=6. For e core-core double
edges and m_u hub-incident doubles, core accounting plus the missing-core-pair
common-neighbour bound gives OW_CORE >= 116 - 8e + 6*m_u; +6*m_u is the hub
contribution. Accepted zero-graph floors are 84 for e=0..4, 80 for e=5, and
78 for e=6. Across the 27 states 0<=e<=6, 0<=m_u<=min(e,5), this gives OW>=78.
Each triangle closes three distinct centered wedges, so OW=W-3*T and
T<=floor((827-78)/3)=249. The state check is arithmetic regression; it does
not replace these analytic inequalities.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROFILE_ID = "65555555555541000000"
FROZEN_HEAD = "e6fee5ebbfb972a1432bbc10ab5a337feac38478"
FROZEN_TREE = "0f32a6e5c813953bb902cce395b5b6fea0a77c59"
FROZEN_RESULT_PATH = "docs/research/matrix-native-results/b649-k20-min-s2-neighbor-deficit-sts13-family-closure-r1-result.json"
FROZEN_RESULT_SHA256 = "fef709c5168afa6da26ce18e0be78c40a12c6a711dec364e42659e1bb309d7b6"
CERTIFICATE_RESULT_PATH = "docs/research/matrix-native-results/b649-k20-min-s2-shared-neighbor-deficit-certificate-r1-result.json"
CERTIFICATE_RESULT_SHA256 = "4e7b8163846f6b87c561fc7a96f12a18c46636ee66c9d0dfdd0b24eb1ec08dfa"
R30_RESULT_PATH = "docs/research/matrix-native-results/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
OLD_CAP, NEW_CAP, OW_FLOOR, W = 265, 249, 78, 827
OLD_BOUND, NEW_BOUND, IMPROVEMENT = 313256489, 313121137, 135352
OLD_ROW_BOUND, NEW_ROW_BOUND, ROW_IMPROVEMENT = OLD_BOUND, NEW_BOUND, IMPROVEMENT
INCUMBENT, INCUMBENT_MARGIN = 313263888, 142751
R30_INDEX = 3397
ROW_BOUND_SOURCE_COLUMN = "BOUND"
ROW_BOUND_SOURCE_METHOD = "Maximum of stored per-T BOUND fields; no formula recomputation."
FULL_FAMILY_CLOSURE_STATUS = "NOT_CLAIMED"
RESULT_SOURCE_IDENTITY = {
    "TASK_ID": "B649_K20_E6FEE5EB_T249_EVIDENCE_ADOPTION_R1",
    "FROZEN_HEAD": FROZEN_HEAD,
    "FROZEN_TREE": FROZEN_TREE,
    "FROZEN_RESULT_PATH": FROZEN_RESULT_PATH,
    "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
    "PROOF_SOURCE_PATH": CERTIFICATE_RESULT_PATH,
    "PROOF_SOURCE_SHA256": CERTIFICATE_RESULT_SHA256,
    "R30_LEDGER_PATH": R30_RESULT_PATH,
    "R30_LEDGER_SHA256": R30_RESULT_SHA256,
    "HISTORICAL_R30_LOCATOR": f"GROUP_ATTEMPTS[{R30_INDEX}]",
    "HISTORICAL_T_CAP": OLD_CAP,
}
ZERO_GRAPH_CASE_FLOORS = {0: 84, 1: 84, 2: 84, 3: 84, 4: 84, 5: 80, 6: 78}


class AdoptionError(ValueError):
    """Pinned evidence or the one-row proposal is inconsistent."""


@dataclass(frozen=True)
class PinnedSources:
    family: dict[str, Any]
    certificate: dict[str, Any]
    r30: dict[str, Any]
    digests: dict[str, str]


def load_pinned_sources(root: Path) -> PinnedSources:
    def read(path: str, expected: str) -> tuple[dict[str, Any], str]:
        data = (root / path).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise AdoptionError(f"pinned SHA mismatch: {path}")
        value = json.loads(data)
        if not isinstance(value, dict):
            raise AdoptionError(f"pinned JSON must be an object: {path}")
        return value, digest

    family, family_sha = read(FROZEN_RESULT_PATH, FROZEN_RESULT_SHA256)
    certificate, certificate_sha = read(CERTIFICATE_RESULT_PATH, CERTIFICATE_RESULT_SHA256)
    r30, r30_sha = read(R30_RESULT_PATH, R30_RESULT_SHA256)
    return PinnedSources(family, certificate, r30, {
        FROZEN_RESULT_PATH: family_sha,
        CERTIFICATE_RESULT_PATH: certificate_sha,
        R30_RESULT_PATH: r30_sha,
    })


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise AdoptionError(message)


def _target_bound(rows: list[list[Any]], profile: str) -> int:
    matches = [row[1] for row in rows if row[0] == profile]
    _need(len(matches) == 1, "target must occur once in COMPLETE_PROFILE_BOUNDS")
    return matches[0]


def verify_integer_states(floors: dict[int, int] | None = None) -> tuple[dict[str, int], ...]:
    floors = ZERO_GRAPH_CASE_FLOORS if floors is None else floors
    _need(floors == ZERO_GRAPH_CASE_FLOORS, "zero-graph correction must include e=0..6 accepted floors")
    states = tuple(
        {"e": e, "m_u": m, "core_accounting_bound": 116 - 8 * e + 6 * m,
         "zero_graph_case_floor": floors[e],
         "ow_lower_bound": max(116 - 8 * e + 6 * m, floors[e])}
        for e in range(7) for m in range(min(e, 5) + 1)
    )
    _need(len(states) == 27 and min(s["ow_lower_bound"] for s in states) >= OW_FLOOR,
          "the 27 accepted integer states must imply OW>=78")
    return states


def verify_wedge_disjointness(total: int, triangles: int, wedges: tuple[tuple[Any, ...], ...]) -> int:
    _need(len(wedges) == 3 * triangles, "each triangle must contribute three wedges")
    _need(len(set(wedges)) == len(wedges), "the same wedge was counted more than once")
    _need(total >= len(wedges), "closed wedges exceed total wedges")
    return total - len(wedges)


def apply_single_target_update(rows: list[list[Any]], updates: dict[str, int]) -> list[list[Any]]:
    _need(set(updates) == {PROFILE_ID}, "only the target profile row may be updated")
    result = [list(row) for row in rows]
    indexes = [i for i, row in enumerate(result) if row[0] == PROFILE_ID]
    _need(len(indexes) == 1 and result[indexes[0]][1] == OLD_BOUND, "old target row mismatch")
    result[indexes[0]][1] = updates[PROFILE_ID]
    _need(all(result[i] == row for i, row in enumerate(rows) if row[0] != PROFILE_ID),
          "a non-target profile row changed")
    return result


def verify_adoption(
    sources: PinnedSources, *, profile_id: str = PROFILE_ID,
    source_sha256: str = CERTIFICATE_RESULT_SHA256, original_cap: int = OLD_CAP,
    accepted_cap: int = NEW_CAP, ow_floor: int = OW_FLOOR,
    zero_graph_floors: dict[int, int] | None = None,
    declared_new_row_bound: int = NEW_BOUND, row_updates: dict[str, int] | None = None,
) -> dict[str, Any]:
    _need(profile_id == PROFILE_ID, "profile ID does not match fixed target")
    _need(source_sha256 == sources.digests[CERTIFICATE_RESULT_PATH] == CERTIFICATE_RESULT_SHA256,
          "certificate source SHA mismatch")
    _need(original_cap == OLD_CAP, "historical R30 cap must remain 265")
    _need(accepted_cap == NEW_CAP, "accepted analytic T cap must remain 249")
    _need(ow_floor == OW_FLOOR, "accepted OW floor must remain 78")
    _need((W - ow_floor) // 3 == accepted_cap, "OW floor does not imply T cap 249")
    states = verify_integer_states(zero_graph_floors)

    family, cert, r30 = sources.family, sources.certificate, sources.r30
    family_rows, cert_rows = family["COMPLETE_PROFILE_BOUNDS"], cert["COMPLETE_PROFILE_BOUNDS"]
    old = _target_bound(family_rows, profile_id)
    _need(old == _target_bound(cert_rows, profile_id) == OLD_BOUND,
          "fixed candidate old target bound changed")
    _need(profile_id in cert["ACTIVE_PROFILE_IDS"], "target missing from ACTIVE_PROFILE_IDS")
    active = cert["ACTIVE_CERTIFICATES"][profile_id]
    _need(active["PROFILE_ID"] == profile_id and active["T_RANGE"] == [22, OLD_CAP],
          "active certificate identity or T range mismatch")
    authority = active["CAP_AUTHORITY"]
    _need(authority["TRIANGLE_CAP"] == original_cap, "active certificate original cap mismatch")
    identity = authority["IDENTITY"]
    _need(identity["PROFILE_IDS"] == [profile_id] and identity["TARGET_TRIANGLE_CAP"] == original_cap,
          "cap authority identity mismatch")

    attempt = r30["GROUP_ATTEMPTS"][R30_INDEX]
    _need(attempt["ATTEMPT_INDEX"] == R30_INDEX and attempt["PROFILE_IDS"] == [profile_id],
          "historical R30 locator/profile mismatch")
    _need(attempt["TARGET_TRIANGLE_CAP"] == original_cap and attempt["STATUS"] == "INFEASIBLE",
          "historical R30 cap certificate mismatch")

    columns = cert["TERM_COLUMNS"]
    _need(columns.count("T") == columns.count(ROW_BOUND_SOURCE_COLUMN) == 1,
          "per-T columns must name T and BOUND")
    ti, bi = columns.index("T"), columns.index(ROW_BOUND_SOURCE_COLUMN)
    by_t = {}
    for row in active["ALL_T_TERMS"]:
        t = row[ti]
        _need(t not in by_t, "duplicate per-T row")
        by_t[t] = row[bi]
    _need(set(by_t) == set(range(22, OLD_CAP + 1)), "per-T rows must cover T=22..265")
    before = [by_t[t] for t in range(22, OLD_CAP + 1)]
    after = [by_t[t] for t in range(22, accepted_cap + 1)]
    old_bound, new_bound = max(before), max(after)
    _need(len(before) == 244 and old_bound == OLD_BOUND == active["CERTIFIED_PROFILE_BOUND"],
          "old per-T BOUND aggregate mismatch")
    _need(len(after) == 228 and new_bound == NEW_BOUND == declared_new_row_bound,
          "new row bound does not match per-T BOUND aggregate")
    incumbent = family["CANONICAL_INCUMBENT"]
    _need(old_bound - new_bound == IMPROVEMENT and incumbent - new_bound == INCUMBENT_MARGIN,
          "row improvement or incumbent margin mismatch")

    updates = {profile_id: new_bound} if row_updates is None else row_updates
    _need(set(updates) == {profile_id} and updates[profile_id] == new_bound,
          "proposal must update only the target to the computed bound")
    proposed = apply_single_target_update(family_rows, updates)
    return {
        "PROFILE_ID": profile_id, "ORIGINAL_CAP": original_cap, "NEW_CAP": accepted_cap,
        "OW_LOWER_BOUND": ow_floor, "INTEGER_STATES": states, "INTEGER_STATE_COUNT": len(states),
        "COMPLETE_PROFILE_BOUND_BEFORE": old, "PER_T_BEFORE_COUNT": len(before),
        "PER_T_AFTER_COUNT": len(after), "OLD_ROW_BOUND": old_bound, "NEW_ROW_BOUND": new_bound,
        "ROW_IMPROVEMENT": old_bound - new_bound, "INCUMBENT": incumbent,
        "INCUMBENT_MARGIN": incumbent - new_bound,
        "OTHER_ROWS_UNCHANGED": all(
            proposed[i] == row for i, row in enumerate(family_rows) if row[0] != profile_id
        ),
        "PROPOSED_COMPLETE_PROFILE_BOUNDS": proposed,
    }


def validate_result_status(result: dict[str, Any], evidence: dict[str, Any]) -> None:
    statuses = {
        "MATHEMATICS": "ACCEPTED", "ARTIFACT": "PASS", "ORIGINAL_RESOURCE": "FAIL",
        "NEW_LOCAL_ADOPTION": "SELF_CHECK_ONLY", "FRESH_JUDGE_OF_NEW_ARTIFACT": "NOT_RUN",
        "FULL_FAMILY_MATHEMATICS": "NOT_VERIFIED", "FULL_FAMILY_BOUND_CLAIM": "NOT_PROMOTED",
        "LOCAL_ARTIFACT_VERDICT": "SELF_CHECK_ONLY", "NEW_ARTIFACT_RESOURCE": "FAIL",
    }
    for key, expected in statuses.items():
        actual = result.get(key)
        _need(type(actual) is str and actual == expected, f"status preservation failed: {key}")
    for key, expected in RESULT_SOURCE_IDENTITY.items():
        actual = result.get(key)
        _need(type(actual) is type(expected) and actual == expected,
              f"result source identity mismatch: {key}")
    fields = {
        "PROFILE_ID": "PROFILE_ID", "OLD_CAP": "ORIGINAL_CAP", "NEW_CAP": "NEW_CAP",
        "OW_LOWER_BOUND": "OW_LOWER_BOUND", "PER_T_BEFORE_COUNT": "PER_T_BEFORE_COUNT",
        "PER_T_AFTER_COUNT": "PER_T_AFTER_COUNT", "OLD_ROW_BOUND": "OLD_ROW_BOUND",
        "NEW_ROW_BOUND": "NEW_ROW_BOUND", "ROW_IMPROVEMENT": "ROW_IMPROVEMENT",
        "INCUMBENT_MARGIN": "INCUMBENT_MARGIN",
    }
    for result_key, evidence_key in fields.items():
        actual, expected = result.get(result_key), evidence[evidence_key]
        _need(type(actual) is type(expected) and actual == expected,
              f"result record mismatch: {result_key}")
    row_bound = result.get("ROW_BOUND_EVIDENCE")
    _need(type(row_bound) is dict, "result record mismatch: ROW_BOUND_EVIDENCE")
    row_bound_fields = {
        "SOURCE_METHOD": ROW_BOUND_SOURCE_METHOD,
        "SOURCE_COLUMN": ROW_BOUND_SOURCE_COLUMN,
    }
    for key, expected in row_bound_fields.items():
        actual = row_bound.get(key)
        _need(type(actual) is type(expected) and actual == expected,
              f"result record evidence mismatch: ROW_BOUND_EVIDENCE.{key}")
    closure = result.get("FULL_FAMILY_CLOSURE")
    _need(type(closure) is str and closure == FULL_FAMILY_CLOSURE_STATUS,
          "result proof scope mismatch: FULL_FAMILY_CLOSURE")
    unchanged = result.get("OTHER_ROWS_UNCHANGED")
    _need(type(unchanged) is str and unchanged == "YES",
          "other profile rows must remain unchanged")
