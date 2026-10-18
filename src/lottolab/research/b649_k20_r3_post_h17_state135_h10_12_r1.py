"""Adopt the State135 H10 certificate for twelve members and vectors.

The module reads the committed H17 Family result and the sealed State135
ledger from the H13 result. It updates only the twelve P_j/Q_j rows, preserves
the remaining ledger, and recomputes the complete Family term digest.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import (
    b649_k20_r3_post_h13_112_member_dual_certificate_r1 as legacy,
)

CountVector = tuple[int, ...]

TASK_ID = "B649_K20_R3_POST_H17_STATE135_H10_12_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-h13-112-member-dual-certificate-r1"
BASE_HEAD = "f6d609143aa4e647c733a315bffdaccecd0e2b1f"
BASE_TREE = "26f90a34f58e7331b8687ba204e2c29cc5df9939"

REPO_ROOT = Path(__file__).resolve().parents[3]
H17_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-post-112-state131-h17-core-r1-result.json"
)
H17_SOURCE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_post_112_state131_h17_core_r1.py"
)
H13_RESULT_RELATIVE = legacy.RESULT_RELATIVE
H13_SOURCE_RELATIVE = (
    "src/lottolab/research/"
    "b649_k20_r3_post_h13_112_member_dual_certificate_r1.py"
)
ROOT_SOURCE_RELATIVE = (
    "src/lottolab/research/"
    "b649_k20_r3_post_h11_h16_paired_root_150_member_certificate_r1.py"
)
HUNTER_SOURCE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_preserved_eleven_hunter_certificate_r1.py"
)
FAMILY_SOURCE_RELATIVE = (
    "src/lottolab/research/"
    "b649_k20_r3_post_h13_two_state_h11_h16_14_member_r1.py"
)
CLASSIFIED_INPUT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-state-14696976-universal-hunter-certificate-r1-result.json"
)

RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-post-h17-state135-h10-12-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE

STATE135 = "state:s2-13548976-s3-951748"
STATE12692531 = "state:s2-12692531-s3-681744"
STATE131_TARGET = "[0,17][25,1]"

EXPECTED_H17_RESULT_SHA256 = (
    "5d93433252d6d517061b93c3573123f64e31ca6d36baf52db85d978db94ba08b"
)
EXPECTED_INPUT_SHA256 = {
    H13_RESULT_RELATIVE: (
        "bf77f1e319016052e46ccb6485e07fb288b150487aa2decc31fe47e1cbc520ee"
    ),
    H17_SOURCE_RELATIVE: (
        "a30b2bef000aa4f1668701e3465ad827ec762cd15aa19985d242a4a2ad913ee7"
    ),
    H13_SOURCE_RELATIVE: (
        "913ca180cf90e63ffb9e2a468a4ebdc4b1bb01ad924b6bd4f0a58958c10622c5"
    ),
    ROOT_SOURCE_RELATIVE: (
        "2a9adfc7b2b170b67effcbc2de97e5bf4272e64e10282ea3cc2079499f5bcd53"
    ),
    HUNTER_SOURCE_RELATIVE: (
        "28c80d2da1fa5a26d10b5005a2eb337c4d09389d36c545afced40adb8895957b"
    ),
    FAMILY_SOURCE_RELATIVE: (
        "11f939e4e1d81062dc09243640f9400e53ebd02db972d9cf64756de2146e343c"
    ),
    CLASSIFIED_INPUT_RELATIVE: (
        "2680e9b1f396991336690ee7660998c4a010c6f14efef40c77e601e3d3280834"
    ),
}
EXPECTED_BASELINE_FAMILY_DIGEST = (
    "bf3f3df1496ab353813e4d8f400fae6eb7c837509a6b9c7375cd7f48f8aea074"
)
EXPECTED_FINAL_FAMILY_DIGEST = (
    "717200d3f34b6cd24de7518d0b1db950a4da34c56c1f9fccdd07606e9f94f26b"
)
EXPECTED_H10_CREDIT = 3_767_400
EXPECTED_BASELINE_FAMILY_UB = 354_981_375
EXPECTED_FINAL_FAMILY_UB = 354_980_829
EXPECTED_STATE135_UB = 354_980_479
EXPECTED_P_UNCORRECTED = 358_425_375
EXPECTED_Q_UNCORRECTED = 358_424_927
EXPECTED_EXISTING_CREDIT = 3_444_000
EXPECTED_P_NEW_BOUND = 354_657_975
EXPECTED_Q_NEW_BOUND = 354_657_527
EXPECTED_PRESERVED_REMAINDER_MAX = 354_980_479
EXPECTED_TARGET_MEMBERS = 12
EXPECTED_TARGET_VECTORS = 12
EXPECTED_STATE135_MEMBERS = 1_427
EXPECTED_STATE135_VECTORS = 1_543
EXPECTED_PRESERVED_MEMBERS = 1_415
EXPECTED_PRESERVED_VECTORS = 1_531
EXPECTED_FAMILY_TERMS = 56_574
EXPECTED_CLASSIFIED_TERMS = 56_550

FLOORS = (107_800, 574_000, 1_691_620, 3_451_651)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def _base_blob(relative: str) -> bytes:
    return _git_bytes("show", f"{BASE_HEAD}:{relative}")


def _file_sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _read_base_json(relative: str) -> dict[str, Any]:
    data = _base_blob(relative)
    working_path = REPO_ROOT / relative
    require(working_path.is_file(), f"required committed input is missing: {relative}")
    require(
        working_path.read_bytes() == data,
        f"input differs from the pinned BASE_HEAD blob: {relative}",
    )
    return cast(dict[str, Any], json.loads(data))


def verify_source_authority() -> dict[str, Any]:
    identity = _git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
    require(identity == f"{BASE_HEAD} {BASE_TREE}", "fixed base HEAD/tree mismatch")
    require(
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
            check=False,
        ).returncode
        == 0,
        "checkout no longer descends from the fixed base",
    )
    branch = _git_bytes("branch", "--show-current").decode().strip()
    require(branch == TASK_BRANCH, "worktree is not on the fixed task branch")

    paths = (H17_RESULT_RELATIVE, *EXPECTED_INPUT_SHA256)
    hashes: dict[str, str] = {}
    for relative in paths:
        base_data = _base_blob(relative)
        working_path = REPO_ROOT / relative
        require(working_path.is_file(), f"required input is missing: {relative}")
        working_data = working_path.read_bytes()
        require(working_data == base_data, f"input differs from BASE_HEAD: {relative}")
        hashes[relative] = _file_sha(base_data)

    require(
        hashes[H17_RESULT_RELATIVE] == EXPECTED_H17_RESULT_SHA256,
        "committed H17 result SHA256 mismatch",
    )
    for relative, expected in EXPECTED_INPUT_SHA256.items():
        require(hashes[relative] == expected, f"pinned input SHA256 mismatch: {relative}")

    h17 = cast(dict[str, Any], json.loads(_base_blob(H17_RESULT_RELATIVE)))
    h17_authority = h17["SOURCE_AUTHORITY"]
    upstream_hashes = h17_authority["input_sha256"]
    for relative in (
        H13_RESULT_RELATIVE,
        H13_SOURCE_RELATIVE,
        ROOT_SOURCE_RELATIVE,
        HUNTER_SOURCE_RELATIVE,
        FAMILY_SOURCE_RELATIVE,
        CLASSIFIED_INPUT_RELATIVE,
    ):
        require(
            upstream_hashes[relative] == hashes[relative],
            f"H17 sealed input hash disagrees with the pinned blob: {relative}",
        )
    require(
        h17_authority["baseline_result"] == H13_RESULT_RELATIVE
        and h17_authority["baseline_result_sha256"] == hashes[H13_RESULT_RELATIVE],
        "H17 result does not bind the expected H13 ledger result",
    )
    return {
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "h17_result": H17_RESULT_RELATIVE,
        "h17_result_sha256": hashes[H17_RESULT_RELATIVE],
        "h13_result": H13_RESULT_RELATIVE,
        "h13_result_sha256": hashes[H13_RESULT_RELATIVE],
        "input_sha256": hashes,
    }


def read_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    h17 = _read_base_json(H17_RESULT_RELATIVE)
    h13 = _read_base_json(H13_RESULT_RELATIVE)
    classified = _read_base_json(CLASSIFIED_INPUT_RELATIVE)
    return h17, h13, classified


def _target_vector(counts: dict[int, int]) -> CountVector:
    return tuple(counts.get(index, 0) for index in range(30))


def target_specs() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for j in range(6):
        for kind, counts in (
            ("P", {0: 10, 1: j, 4: 5 - j, 5: 2, 20: 1}),
            ("Q", {0: 10, 1: j, 4: 5 - j, 5: 1, 16: 1, 20: 1}),
        ):
            vector = _target_vector(counts)
            sparse = legacy.sparse(vector)
            specs.append(
                {
                    "cohort": kind,
                    "j": j,
                    "vector": vector,
                    "counts": sparse,
                    "member_id": legacy.member_id(vector),
                }
            )
    require(len(specs) == EXPECTED_TARGET_MEMBERS, "P/Q target cardinality changed")
    require(
        len({item["member_id"] for item in specs}) == EXPECTED_TARGET_MEMBERS
        and len({item["vector"] for item in specs}) == EXPECTED_TARGET_VECTORS,
        "P/Q targets are not distinct members and vectors",
    )
    return tuple(specs)


def _previous_correction_members(h13: dict[str, Any], h17: dict[str, Any]) -> set[str]:
    baseline = h13["BASELINE_CORRECTIONS"]
    baseline_ids = [str(member_id) for ids in baseline.values() for member_id in ids]
    require(len(baseline_ids) == 74, "112/123 predecessor member count changed")
    novel_ids = [
        str(certificate["member_id"])
        for region in h13["REGIONS"]
        for certificate in region["member_certificates"]
    ]
    novel_vectors = sum(
        int(certificate["represented_vector_count"])
        for region in h13["REGIONS"]
        for certificate in region["member_certificates"]
    )
    require(len(novel_ids) == 38 and novel_vectors == 39, "112/123 novel target scope changed")
    ids = baseline_ids + novel_ids
    require(len(set(ids)) == 112, "112/123 member correction scope is not distinct")
    ids.append(str(h17["STATE131"]["target_member_id"]))
    require(
        len(set(ids)) == 113 and STATE131_TARGET in ids,
        "H17 extension does not have 113 distinct predecessor corrections",
    )
    require(
        h17["BASELINE_112_123"]["combined_members"] == 113
        and h17["BASELINE_112_123"]["combined_vectors"] == 124,
        "H17 result does not seal the 113/124 predecessor scope",
    )
    return set(ids)


def validate_h10_certificate(proof: dict[str, Any]) -> None:
    core = cast(dict[str, Any], json.loads(legacy.encode(legacy.paired.core_proof(10))))
    hunter = legacy.hunter
    rows = hunter.exact_pair_rows(((0, 0),))
    floors = hunter.pair_floors(rows)
    require(floors == FLOORS, "H10 exact type-0 pair floors changed")
    require(
        tuple(row[6] for row in rows) == FLOORS,
        "H10 pair rows do not attain the four sealed floors",
    )
    require(
        core["event_count"] == 10
        and core["outside_incidences"] == 60
        and core["outside_labels"] == 40
        and core["collision_floor"] == 20
        and core["threshold_cases"] == 16_982
        and tuple(core["minimizer"]) == (20, 0, 0)
        and tuple(core["ranks"]) == (6, 0, 0)
        and core["hunter_floor"] == EXPECTED_H10_CREDIT,
        "H10 universal threshold minimum differs from the sealed certificate",
    )
    require(
        hunter.tree_weight_floor(floors, core["ranks"], 10) == EXPECTED_H10_CREDIT,
        "H10 exact core floor formula changed",
    )

    core_edges = tuple((0, index) for index in range(1, 10))
    leaf_edges = tuple((0, index) for index in range(10, 18))
    full_edges = legacy.paired.validate_tree_extension(
        tuple(range(10)), core_edges, leaf_edges
    )
    expected = {
        "core_type": 0,
        "core_event_count": 10,
        "core_pair_rows": [list(row) for row in rows],
        "core_pair_floors": list(floors),
        "threshold_minimum": core,
        "credit": EXPECTED_H10_CREDIT,
        "credit_rule": "H10 core credit only; subtract once using MAX(existing, H10)",
        "tree_extension": {
            "core_tree_selection": (
                "support-specific descending Kruskal threshold tree; 9 core edges"
            ),
            "topology_example_only": [list(edge) for edge in core_edges],
            "leaf_edges": [list(edge) for edge in leaf_edges],
            "leaf_edge_credits": [0] * 8,
            "leaf_credit_total": 0,
            "vertices": 18,
            "edges": 17,
            "distinct_edges": len({frozenset(edge) for edge in full_edges}),
            "is_tree": hunter.graph_rank(18, full_edges) == 17,
            "universal_argument": legacy.paired.prior.__doc__,
        },
        "proof_scope": "ALL_LEGAL_SUPPORTS",
        "witness_used_as_proof": False,
        "pointwise_hunter_inequality": (
            "For every outcome, the subgraph induced by its present residual "
            "events is a forest with at most max(m-1, 0) edges. Thus the union "
            "indicator is bounded by the sum of event indicators minus the "
            "sum of intersection indicators on the selected tree."
        ),
    }
    require(proof == expected, "H10 certificate or zero-credit tree differs from replay")


def build_h10_certificate() -> dict[str, Any]:
    core = cast(dict[str, Any], json.loads(legacy.encode(legacy.paired.core_proof(10))))
    hunter = legacy.hunter
    rows = hunter.exact_pair_rows(((0, 0),))
    floors = hunter.pair_floors(rows)
    core_edges = tuple((0, index) for index in range(1, 10))
    leaf_edges = tuple((0, index) for index in range(10, 18))
    full_edges = legacy.paired.validate_tree_extension(
        tuple(range(10)), core_edges, leaf_edges
    )
    proof = {
        "core_type": 0,
        "core_event_count": 10,
        "core_pair_rows": [list(row) for row in rows],
        "core_pair_floors": list(floors),
        "threshold_minimum": core,
        "credit": EXPECTED_H10_CREDIT,
        "credit_rule": "H10 core credit only; subtract once using MAX(existing, H10)",
        "tree_extension": {
            "core_tree_selection": (
                "support-specific descending Kruskal threshold tree; 9 core edges"
            ),
            "topology_example_only": [list(edge) for edge in core_edges],
            "leaf_edges": [list(edge) for edge in leaf_edges],
            "leaf_edge_credits": [0] * 8,
            "leaf_credit_total": 0,
            "vertices": 18,
            "edges": 17,
            "distinct_edges": len({frozenset(edge) for edge in full_edges}),
            "is_tree": hunter.graph_rank(18, full_edges) == 17,
            "universal_argument": legacy.paired.prior.__doc__,
        },
        "proof_scope": "ALL_LEGAL_SUPPORTS",
        "witness_used_as_proof": False,
        "pointwise_hunter_inequality": (
            "For every outcome, the subgraph induced by its present residual "
            "events is a forest with at most max(m-1, 0) edges. Thus the union "
            "indicator is bounded by the sum of event indicators minus the "
            "sum of intersection indicators on the selected tree."
        ),
    }
    validate_h10_certificate(proof)
    return proof


def _vector_projection(members: list[dict[str, Any]]) -> tuple[Any, ...]:
    return tuple(
        (
            str(member["member_id"]),
            int(member["final_bound"]),
            tuple(
                (
                    tuple(tuple(int(value) for value in pair) for pair in row["counts"]),
                    int(row["final_bound"]),
                )
                for row in member["represented_vector_bounds"]
            ),
        )
        for member in members
    )


def _validate_member_max(member: dict[str, Any]) -> None:
    rows = member.get("represented_vector_bounds")
    if rows is None:
        represented = member.get("represented_vectors")
        require(isinstance(represented, list) and bool(represented), "member lacks represented vectors")
        rows = [
            {"counts": counts, "final_bound": int(member["final_bound"])}
            for counts in represented
        ]
    require(isinstance(rows, list) and bool(rows), "member lacks represented vector bounds")
    require(
        len(rows) == int(member["represented_vector_count"]),
        f"member/vector cardinality mismatch: {member['member_id']}",
    )
    bounds = [int(row["final_bound"]) for row in rows]
    require(
        int(member["final_bound"]) == max(bounds),
        f"compressed member must take MAX of represented-vector bounds: {member['member_id']}",
    )
    if "new_bound" in member:
        require(
            int(member["new_bound"]) == int(member["final_bound"]),
            f"member new_bound is stale: {member['member_id']}",
        )
    for row in rows:
        if "new_bound" in row:
            require(
                int(row["new_bound"]) == int(row["final_bound"]),
                f"vector new_bound is stale: {member['member_id']}",
            )


def _target_tree(vector: CountVector) -> dict[str, Any]:
    event_types = tuple(
        event_type for event_type, count in enumerate(vector) for _ in range(count)
    )
    require(
        len(event_types) == 18 and event_types[:10] == (0,) * 10,
        "P/Q target must contain a ten-event type-0 core and eight leaves",
    )
    core_edges = tuple((0, index) for index in range(1, 10))
    leaf_edges = tuple((0, index) for index in range(10, 18))
    full_edges = legacy.paired.validate_tree_extension(
        tuple(range(10)), core_edges, leaf_edges
    )
    return {
        "core_event_count": 10,
        "leaf_event_count": 8,
        "leaf_event_types": list(event_types[10:]),
        "topology_example_only": [list(edge) for edge in core_edges],
        "leaf_edges": [list(edge) for edge in leaf_edges],
        "leaf_edge_credits": [0] * 8,
        "vertices": 18,
        "edges": 17,
        "distinct_edges": len({frozenset(edge) for edge in full_edges}),
        "is_tree": legacy.hunter.graph_rank(18, full_edges) == 17,
    }


def corrected_bound(uncorrected: int, existing_credit: int, h10_credit: int) -> int:
    if any(type(value) is not int for value in (uncorrected, existing_credit, h10_credit)):
        raise TypeError("bounds and credits must be exact integers")
    if min(uncorrected, existing_credit, h10_credit) < 0:
        raise ValueError("bounds and credits must be nonnegative")
    return uncorrected - max(existing_credit, h10_credit)


def apply_state135(
    h13: dict[str, Any],
    h17: dict[str, Any],
    proof: dict[str, Any],
    existing_correction_ids: set[str],
    member_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_h10_certificate(proof)
    source_region = next(
        (region for region in h13["REGIONS"] if region["state_id"] == STATE135),
        None,
    )
    require(source_region is not None, "State135 source region is missing")
    members = copy.deepcopy(
        source_region["complete_region_members"] if member_rows is None else member_rows
    )
    require(
        len(members) == EXPECTED_STATE135_MEMBERS,
        "State135 canonical member count changed",
    )
    require(
        sum(int(member["represented_vector_count"]) for member in members)
        == EXPECTED_STATE135_VECTORS,
        "State135 represented-vector count changed",
    )
    member_map = {str(member["member_id"]): member for member in members}
    require(len(member_map) == len(members), "duplicate canonical member in State135")
    for member in members:
        _validate_member_max(member)

    specs = target_specs()
    target_ids = {str(spec["member_id"]) for spec in specs}
    require(
        len(target_ids) == EXPECTED_TARGET_MEMBERS and not target_ids.intersection(existing_correction_ids),
        "State135 targets overlap the existing 113/124 corrections",
    )
    require(
        target_ids <= member_map.keys(),
        "one or more exact P_j/Q_j target members are absent from State135",
    )
    require(
        len(target_ids.intersection(member_map.keys())) == EXPECTED_TARGET_MEMBERS,
        "P_j/Q_j target member coverage is incomplete",
    )

    target_aliases = 0
    prior_aliases = h13.get("COMPRESSED_ALIASES", {})
    for group in prior_aliases.values():
        for alias in group:
            if (
                str(alias.get("canonical_member_id")) in target_ids
                or any(counts in [spec["counts"] for spec in specs] for counts in alias.get("represented_vectors", []))
            ):
                target_aliases += 1
    require(target_aliases == 0, "a target is represented by a compressed alias")

    before_preserved = _vector_projection(
        [member for member in members if str(member["member_id"]) not in target_ids]
    )
    records: list[dict[str, Any]] = []
    for spec in specs:
        member = member_map[str(spec["member_id"])]
        vector_rows = member.get("represented_vector_bounds")
        require(
            isinstance(vector_rows, list) and len(vector_rows) == 1,
            f"target must represent exactly one vector: {spec['member_id']}",
        )
        vector_row = vector_rows[0]
        vector = tuple(legacy.dense(vector_row["counts"]))
        require(
            vector == spec["vector"]
            and vector_row["counts"] == spec["counts"]
            and member.get("represented_vectors") == [spec["counts"]],
            f"canonical P_j/Q_j represented vector mismatch: {spec['member_id']}",
        )
        require(
            int(member["represented_vector_count"]) == 1
            and legacy.member_id(vector) == str(spec["member_id"]),
            f"target alias or canonical member identity mismatch: {spec['member_id']}",
        )
        prior_bound = int(vector_row["final_bound"])
        require(
            int(member["final_bound"]) == prior_bound,
            f"target member/vector bounds differ: {spec['member_id']}",
        )
        uncorrected = int(legacy.uncorrected_bound(vector))
        existing_credit = uncorrected - prior_bound
        require(existing_credit == EXPECTED_EXISTING_CREDIT, "target existing credit changed")
        h10_credit = int(proof["credit"])
        effective_credit = max(existing_credit, h10_credit)
        new_bound = corrected_bound(uncorrected, existing_credit, h10_credit)
        expected_uncorrected = (
            EXPECTED_P_UNCORRECTED if spec["cohort"] == "P" else EXPECTED_Q_UNCORRECTED
        )
        expected_bound = EXPECTED_P_NEW_BOUND if spec["cohort"] == "P" else EXPECTED_Q_NEW_BOUND
        require(
            (uncorrected, existing_credit, h10_credit, effective_credit, new_bound)
            == (
                expected_uncorrected,
                EXPECTED_EXISTING_CREDIT,
                EXPECTED_H10_CREDIT,
                EXPECTED_H10_CREDIT,
                expected_bound,
            ),
            f"target bound arithmetic mismatch: {spec['member_id']}",
        )
        tree = _target_tree(vector)
        vector_row.update(
            {
                "uncorrected_bound": uncorrected,
                "existing_credit": existing_credit,
                "new_core_credit": h10_credit,
                "effective_credit": effective_credit,
                "new_bound": new_bound,
                "final_bound": new_bound,
            }
        )
        member.update(
            {
                "target_cohort": spec["cohort"],
                "target_j": spec["j"],
                "new_core_credit": h10_credit,
                "new_bound": new_bound,
                "final_bound": max(int(row["final_bound"]) for row in vector_rows),
            }
        )
        _validate_member_max(member)
        records.append(
            {
                "cohort": spec["cohort"],
                "j": spec["j"],
                "member_id": str(spec["member_id"]),
                "counts": spec["counts"],
                "uncorrected_bound": uncorrected,
                "prior_bound": prior_bound,
                "existing_credit": existing_credit,
                "h10_credit": h10_credit,
                "effective_credit": effective_credit,
                "new_bound": new_bound,
                "represented_vector_count": 1,
                "target_aliases": 0,
                "tree_extension": tree,
            }
        )

    after_preserved = _vector_projection(
        [member for member in members if str(member["member_id"]) not in target_ids]
    )
    require(before_preserved == after_preserved, "a non-target State135 bound changed")
    preserved = [member for member in members if str(member["member_id"]) not in target_ids]
    preserved_vectors = sum(int(member["represented_vector_count"]) for member in preserved)
    preserved_max = max(int(member["final_bound"]) for member in preserved)
    state_bound = max(int(member["final_bound"]) for member in members)
    require(
        (len(preserved), preserved_vectors, preserved_max, state_bound)
        == (
            EXPECTED_PRESERVED_MEMBERS,
            EXPECTED_PRESERVED_VECTORS,
            EXPECTED_PRESERVED_REMAINDER_MAX,
            EXPECTED_STATE135_UB,
        ),
        "State135 preserved remainder or new maximum mismatch",
    )
    state = {
        "state_id": STATE135,
        "canonical_members": len(members),
        "represented_vectors": sum(int(member["represented_vector_count"]) for member in members),
        "prior_state_bound": int(source_region["new_state_bound"]),
        "target_member_count": len(records),
        "target_vector_count": sum(int(record["represented_vector_count"]) for record in records),
        "target_alias_count": target_aliases,
        "preserved_member_count": len(preserved),
        "preserved_vector_count": preserved_vectors,
        "preserved_remainder_max": preserved_max,
        "preserved_member_vector_bounds_sha256": _file_sha(
            repr(before_preserved).encode("ascii")
        ),
        "preservation_check_sha256": _file_sha(repr(after_preserved).encode("ascii")),
        "new_state_bound": state_bound,
        "target_certificates": records,
        "complete_region_members": members,
    }
    verify_state135_payload(state)
    return state


def verify_state135_payload(state: dict[str, Any]) -> None:
    members = state["complete_region_members"]
    require(len(members) == EXPECTED_STATE135_MEMBERS, "State135 complete ledger is incomplete")
    require(
        sum(int(member["represented_vector_count"]) for member in members)
        == EXPECTED_STATE135_VECTORS,
        "State135 vector ledger is incomplete",
    )
    for member in members:
        _validate_member_max(member)

    specs = target_specs()
    target_ids = {str(spec["member_id"]) for spec in specs}
    member_map = {str(member["member_id"]): member for member in members}
    require(target_ids <= member_map.keys(), "State135 target rows are missing")
    records = state["target_certificates"]
    require(
        len(records) == EXPECTED_TARGET_MEMBERS
        and {str(record["member_id"]) for record in records} == target_ids,
        "State135 target certificate coverage is incomplete",
    )
    for record in records:
        kind = str(record["cohort"])
        uncorrected = int(record["uncorrected_bound"])
        existing = int(record["existing_credit"])
        h10_credit = int(record["h10_credit"])
        effective = int(record["effective_credit"])
        new_bound = int(record["new_bound"])
        require(
            effective == max(existing, h10_credit)
            and new_bound == uncorrected - effective,
            f"target credit must be MAX and subtracted once: {record['member_id']}",
        )
        expected_uncorrected = (
            EXPECTED_P_UNCORRECTED if kind == "P" else EXPECTED_Q_UNCORRECTED
        )
        expected_bound = EXPECTED_P_NEW_BOUND if kind == "P" else EXPECTED_Q_NEW_BOUND
        require(
            (uncorrected, existing, h10_credit, effective, new_bound)
            == (
                expected_uncorrected,
                EXPECTED_EXISTING_CREDIT,
                EXPECTED_H10_CREDIT,
                EXPECTED_H10_CREDIT,
                expected_bound,
            ),
            f"target certificate arithmetic mismatch: {record['member_id']}",
        )
        member = member_map[str(record["member_id"])]
        row = member["represented_vector_bounds"][0]
        require(
            int(member["final_bound"]) == new_bound
            and int(row["final_bound"]) == new_bound
            and int(row["effective_credit"]) == effective
            and int(row["new_bound"]) == new_bound,
            f"target row does not match its certificate: {record['member_id']}",
        )
        require(record["target_aliases"] == 0, "target aliases must be zero")
        require(record["tree_extension"] == _target_tree(tuple(legacy.dense(record["counts"]))),
                f"target tree extension changed: {record['member_id']}")

    preserved = [member for member in members if str(member["member_id"]) not in target_ids]
    preserved_projection = _vector_projection(preserved)
    require(
        (len(preserved), sum(int(m["represented_vector_count"]) for m in preserved),
         max(int(m["final_bound"]) for m in preserved))
        == (
            EXPECTED_PRESERVED_MEMBERS,
            EXPECTED_PRESERVED_VECTORS,
            EXPECTED_PRESERVED_REMAINDER_MAX,
        ),
        "State135 preserved remainder mismatch",
    )
    preservation_sha = _file_sha(repr(preserved_projection).encode("ascii"))
    require(
        state["preserved_member_vector_bounds_sha256"]
        == state["preservation_check_sha256"]
        == preservation_sha,
        "State135 preserved member/vector bounds changed",
    )
    require(
        int(state["new_state_bound"]) == max(int(m["final_bound"]) for m in members)
        == EXPECTED_STATE135_UB,
        "State135 bound differs from the full member ledger",
    )


def _family_terms(
    h17: dict[str, Any], classified: dict[str, Any]
) -> tuple[tuple[str, int], ...]:
    state_terms = tuple(
        (str(row["stable_id"]), int(row["bound"])) for row in h17["FINAL_STATE_TERMS"]
    )
    class_terms = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in classified["FINAL_CLASSIFIED_TERMS"]
    )
    return state_terms + class_terms + (
        ("unclassified-tail", int(classified["TAIL_BOUND"])),
    )


def _terms_digest(terms: tuple[tuple[str, int], ...]) -> str:
    return sha256(repr(tuple(terms)).encode("ascii")).hexdigest()


def build_family(
    h17: dict[str, Any], classified: dict[str, Any], state135_bound: int
) -> dict[str, Any]:
    terms_before = _family_terms(h17, classified)
    require(len(terms_before) == EXPECTED_FAMILY_TERMS, "complete Family term count changed")
    require(
        len({stable_id for stable_id, _ in terms_before}) == EXPECTED_FAMILY_TERMS,
        "complete Family terms contain duplicate identities",
    )
    baseline_digest = _terms_digest(terms_before)
    baseline_max = max(bound for _, bound in terms_before)
    h17_family = h17["FAMILY_RECOMPUTATION"]
    require(
        baseline_digest == EXPECTED_BASELINE_FAMILY_DIGEST
        == h17_family["new_digest"]
        and baseline_max == EXPECTED_BASELINE_FAMILY_UB
        == int(h17["FINAL_COMPLETE_FAMILY_UB"])
        and h17_family["term_count"] == EXPECTED_FAMILY_TERMS,
        "reconstructed H17 Family does not match its sealed result",
    )
    require(
        len(h17["FINAL_STATE_TERMS"]) == 23
        and len(classified["FINAL_CLASSIFIED_TERMS"]) == EXPECTED_CLASSIFIED_TERMS,
        "Family state/classified term partition changed",
    )
    require(
        h17_family["classified_sha256"] == _terms_digest(terms_before[23:-1])
        and h17_family["classified_max"] == max(bound for _, bound in terms_before[23:-1]),
        "classified terms differ from the sealed H17 Family input",
    )
    require(
        terms_before[-1]
        == ("unclassified-tail", int(classified["TAIL_BOUND"]))
        and h17_family["tail"]["bound"] == terms_before[-1][1],
        "Family tail differs from the sealed H17 Family input",
    )

    matching = [
        index for index, (stable_id, _) in enumerate(terms_before) if stable_id == STATE135
    ]
    require(len(matching) == 1, "State135 must occur once in the complete Family")
    index = matching[0]
    terms_after = (
        terms_before[:index]
        + ((STATE135, int(state135_bound)),)
        + terms_before[index + 1 :]
    )
    changed = sum(
        before != after
        for before, after in zip(terms_before, terms_after, strict=True)
    )
    require(
        changed == 1
        and terms_after[23:] == terms_before[23:]
        and all(
            terms_after[i] == terms_before[i]
            for i in range(23)
            if i != index
        ),
        "a non-State135 Family term or its order changed",
    )
    digest = _terms_digest(terms_after)
    ordered = sorted(terms_after, key=lambda term: (-term[1], term[0]))
    owner, runner_up = ordered[0], ordered[1]
    require(
        (digest, owner, runner_up)
        == (
            EXPECTED_FINAL_FAMILY_DIGEST,
            (STATE12692531, EXPECTED_FINAL_FAMILY_UB),
            (STATE135, EXPECTED_STATE135_UB),
        ),
        "complete Family digest, owner, or runner-up mismatch",
    )
    return {
        "term_count": len(terms_after),
        "baseline_digest": baseline_digest,
        "new_digest": digest,
        "changed_terms": changed,
        "preserved_terms": len(terms_after) - changed,
        "baseline_max": baseline_max,
        "final_max": owner[1],
        "owner": {"stable_id": owner[0], "bound": owner[1]},
        "runner_up": {"stable_id": runner_up[0], "bound": runner_up[1]},
        "owner_runner_up_gap": owner[1] - runner_up[1],
        "incremental_gain": baseline_max - owner[1],
        "classified_term_count": len(terms_after[23:-1]),
        "classified_max": max(bound for _, bound in terms_after[23:-1]),
        "classified_sha256": _terms_digest(terms_after[23:-1]),
        "tail": {"stable_id": terms_after[-1][0], "bound": terms_after[-1][1]},
        "final_state_terms": [
            {"stable_id": stable_id, "bound": bound}
            for stable_id, bound in terms_after[:23]
        ],
        "digest_method": "sha256(repr(tuple(terms)).encode('ascii'))",
    }


def validate_inputs(
    h17: dict[str, Any], h13: dict[str, Any], classified: dict[str, Any]
) -> set[str]:
    require(
        h17["TASK_ID"] == "B649_K20_R3_POST_112_STATE131_H17_CORE_R1"
        and h17["TASK_STATUS"] == "SUCCESS",
        "committed H17 result identity/status mismatch",
    )
    require(
        h17["FINAL_COMPLETE_FAMILY_UB"] == EXPECTED_BASELINE_FAMILY_UB
        and h17["FAMILY_RECOMPUTATION"]["new_digest"] == EXPECTED_BASELINE_FAMILY_DIGEST,
        "committed H17 Family baseline mismatch",
    )
    require(
        h13["TASK_ID"] == "B649_K20_R3_POST_H13_112_MEMBER_DUAL_CERTIFICATE_R1"
        and h13["TASK_STATUS"] == "SUCCESS"
        and h13["SOURCE_AUTHORITY_STATUS"] == "PASS_IMMUTABLE_OBJECTS_AND_LIVE_BYTES",
        "committed H13 ledger identity/status mismatch",
    )
    require(
        h13["TOTAL_ADOPTED_MEMBERS"] == 112
        and h13["TOTAL_ADOPTED_VECTORS"] == 123
        and h13["BASELINE_MEMBERS"] == 74
        and h13["BASELINE_VECTORS"] == 84
        and h13["NOVEL_TARGET_MEMBERS"] == 38
        and h13["NOVEL_TARGET_VECTORS"] == 39,
        "112/123 baseline scope changed",
    )
    require(
        len(classified["FINAL_CLASSIFIED_TERMS"]) == EXPECTED_CLASSIFIED_TERMS,
        "classified Family term count changed",
    )
    existing = _previous_correction_members(h13, h17)
    state135_term = next(
        (int(row["bound"]) for row in h17["FINAL_STATE_TERMS"] if row["stable_id"] == STATE135),
        None,
    )
    require(state135_term == EXPECTED_BASELINE_FAMILY_UB, "H17 State135 term changed")
    return existing


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    h17, h13, classified = read_inputs()
    existing_corrections = validate_inputs(h17, h13, classified)
    proof = build_h10_certificate()
    state135 = apply_state135(h13, h17, proof, existing_corrections)
    family = build_family(h17, classified, int(state135["new_state_bound"]))

    specs = target_specs()
    p_specs = [spec for spec in specs if spec["cohort"] == "P"]
    q_specs = [spec for spec in specs if spec["cohort"] == "Q"]
    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "TASK_BRANCH": TASK_BRANCH,
        "IMPLEMENTATION_DEPTH": "NORMAL",
        "DEPTH_SOURCE": "PLANNER_SUPPLIED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "SOURCE_AUTHORITY": authority,
        "H17_BASELINE": {
            "result": H17_RESULT_RELATIVE,
            "result_sha256": authority["h17_result_sha256"],
            "family_ub": EXPECTED_BASELINE_FAMILY_UB,
            "family_digest": EXPECTED_BASELINE_FAMILY_DIGEST,
            "family_terms": EXPECTED_FAMILY_TERMS,
            "classified_terms": EXPECTED_CLASSIFIED_TERMS,
            "preserved_h17_result": True,
        },
        "PREVIOUS_SCOPE": {
            "members": 113,
            "vectors": 124,
            "new_distinct_members": EXPECTED_TARGET_MEMBERS,
            "new_distinct_vectors": EXPECTED_TARGET_VECTORS,
            "cumulative_members": 125,
            "cumulative_vectors": 136,
            "overlap_members": 0,
            "target_aliases": 0,
        },
        "TARGET_COVERAGE": {
            "state_id": STATE135,
            "P_members": len(p_specs),
            "P_vectors": len(p_specs),
            "Q_members": len(q_specs),
            "Q_vectors": len(q_specs),
            "distinct_members": len(specs),
            "represented_vectors": len(specs),
            "target_aliases": 0,
            "existing_correction_overlap": 0,
            "member_ids": [str(spec["member_id"]) for spec in specs],
            "canonical_vectors": [spec["counts"] for spec in specs],
        },
        "H10_CERTIFICATE": proof,
        "TREE_LEGALITY": "PASS_10_CORE_EDGES_PLUS_EIGHT_ZERO_CREDIT_LEAVES",
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_EFFECTIVE_CREDIT_SUBTRACT_ONCE_MEMBER_MAX",
        "STATE135": state135,
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["final_state_terms"],
        "EXPECTED_COMPLETE_FAMILY_GAIN": family["incremental_gain"],
        "FINAL_COMPLETE_FAMILY_UB": family["final_max"],
        "FINAL_OWNER": family["owner"],
        "RUNNER_UP": family["runner_up"],
        "OWNER_RUNNER_GAP": family["owner_runner_up_gap"],
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE_DEPLOY": "NONE",
    }
    return cast(dict[str, Any], json.loads(legacy.encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    validate_h10_certificate(result["H10_CERTIFICATE"])
    verify_state135_payload(result["STATE135"])
    if result != build_result():
        raise AssertionError("result differs from source-bound deterministic replay")
    return {
        "status": "PASS",
        "target_members": result["TARGET_COVERAGE"]["distinct_members"],
        "target_vectors": result["TARGET_COVERAGE"]["represented_vectors"],
        "target_aliases": result["TARGET_COVERAGE"]["target_aliases"],
        "h10_credit": result["H10_CERTIFICATE"]["credit"],
        "new_state135_ub": result["STATE135"]["new_state_bound"],
        "family_ub": result["FINAL_COMPLETE_FAMILY_UB"],
        "family_gain": result["FAMILY_RECOMPUTATION"]["incremental_gain"],
        "family_digest": result["FAMILY_RECOMPUTATION"]["new_digest"],
    }


def verify_stored_result() -> dict[str, Any]:
    data = RESULT_PATH.read_bytes()
    stored = cast(dict[str, Any], json.loads(data))
    summary = verify_result(stored)
    require(
        data == legacy.encode(stored).encode("utf-8"),
        "result bytes are not canonical",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return

    result = build_result()
    if args.write:
        payload = legacy.encode(result).encode("utf-8")
        if RESULT_PATH.exists():
            require(
                RESULT_PATH.read_bytes() == payload,
                "refusing to replace a different result file",
            )
        else:
            require(RESULT_PATH.parent.is_dir(), "authorized result directory is missing")
            RESULT_PATH.write_bytes(payload)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "TARGET_MEMBERS": result["TARGET_COVERAGE"]["distinct_members"],
                "TARGET_VECTORS": result["TARGET_COVERAGE"]["represented_vectors"],
                "H10_CREDIT": result["H10_CERTIFICATE"]["credit"],
                "NEW_STATE135_UB": result["STATE135"]["new_state_bound"],
                "FINAL_FAMILY_UB": result["FINAL_COMPLETE_FAMILY_UB"],
                "COMPLETE_FAMILY_GAIN": result["FAMILY_RECOMPUTATION"]["incremental_gain"],
                "FINAL_FAMILY_DIGEST": result["FAMILY_RECOMPUTATION"]["new_digest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
