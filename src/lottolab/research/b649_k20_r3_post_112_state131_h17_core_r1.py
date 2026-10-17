"""Adopt the universal H17 type-0 core bound for one State131 member.

This is an incremental certificate layered on the sealed 112/123 adoption.
It consumes that result and its existing ledger projection, adds one distinct
member/vector, and recomputes the complete Family maximum and digest.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from functools import cache
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import (
    b649_k20_r3_post_h13_112_member_dual_certificate_r1 as legacy,
)

CountVector = tuple[int, ...]

TASK_ID = "B649_K20_R3_POST_112_STATE131_H17_CORE_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-h13-112-member-dual-certificate-r1"
BASE_HEAD = "9454d5e40ddfd8cafb2e96671eeb0a83144bcae5"
BASE_TREE = "7b6d15d75d5d08b924d13cfba89c9da953301147"
PREVIOUS_RESEARCH_SOURCE = "1a7f8b214c431d4118475cb34f62eeaa1678e6bb"

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_SOURCE_RELATIVE = (
    "src/lottolab/research/"
    "b649_k20_r3_post_h13_112_member_dual_certificate_r1.py"
)
BASELINE_RESULT_RELATIVE = legacy.RESULT_RELATIVE
STATE131_INPUT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-post-h13-two-state-h11-h16-14-member-r1-result.json"
)
CLASSIFIED_INPUT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-state-14696976-universal-hunter-certificate-r1-result.json"
)
ROOT150_INPUT_RELATIVE = legacy.paired.RESULT_RELATIVE
TS153_INPUT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-ts153-four-state-wall-adoption-r2-result.json"
)
HUNTER_SOURCE_RELATIVE = Path(legacy.hunter.__file__).resolve().relative_to(
    REPO_ROOT
).as_posix()
PAIRED_CONTRACT_SOURCE_RELATIVE = Path(legacy.paired.__file__).resolve().relative_to(
    REPO_ROOT
).as_posix()
FAMILY_SOURCE_RELATIVE = Path(legacy.paired.prior.__file__).resolve().relative_to(
    REPO_ROOT
).as_posix()

RESULT_RELATIVE = (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-post-112-state131-h17-core-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE

STATE131 = legacy.STATE_C
STATE135 = legacy.STATE_B
STATE12692531 = legacy.STATE_D
TARGET_MEMBER_ID = "[0,17][25,1]"
TARGET_VECTOR = tuple(17 if index == 0 else 1 if index == 25 else 0 for index in range(30))

EXPECTED_BASELINE_SOURCE_SHA256 = (
    "913ca180cf90e63ffb9e2a468a4ebdc4b1bb01ad924b6bd4f0a58958c10622c5"
)
EXPECTED_BASELINE_RESULT_SHA256 = (
    "bf77f1e319016052e46ccb6485e07fb288b150487aa2decc31fe47e1cbc520ee"
)
EXPECTED_BASELINE_FAMILY_DIGEST = (
    "ed40b014be4d95a310cf4816b1be3f8ca58fa6bb879f5f41af9aeaa194931c95"
)
EXPECTED_FAMILY_DIGEST = (
    "bf3f3df1496ab353813e4d8f400fae6eb7c837509a6b9c7375cd7f48f8aea074"
)
EXPECTED_STATE131_UNTOUCHED_MAX = 354_977_147
EXPECTED_TARGET_PRIOR_BOUND = 354_981_480
EXPECTED_TARGET_UNCORRECTED_BOUND = 362_443_480
EXPECTED_EXISTING_CREDIT = 7_462_000
EXPECTED_H17_CREDIT = 7_785_400
EXPECTED_TARGET_NEW_BOUND = 354_658_080
EXPECTED_FAMILY_UB = 354_981_375

FLOORS = (107_800, 574_000, 1_691_620, 3_451_651)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def _base_blob(relative: str) -> bytes:
    return _git_bytes("show", f"{BASE_HEAD}:{relative}")


def _legacy_blob(relative: str) -> bytes:
    return _git_bytes("show", f"{legacy.BASE_HEAD}:{relative}")


def _file_sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _tracked_source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                BASELINE_SOURCE_RELATIVE,
                BASELINE_RESULT_RELATIVE,
                STATE131_INPUT_RELATIVE,
                CLASSIFIED_INPUT_RELATIVE,
                ROOT150_INPUT_RELATIVE,
                TS153_INPUT_RELATIVE,
                HUNTER_SOURCE_RELATIVE,
                PAIRED_CONTRACT_SOURCE_RELATIVE,
                FAMILY_SOURCE_RELATIVE,
            }
        )
    )


def verify_source_authority() -> dict[str, Any]:
    base_identity = _git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
    require(base_identity == f"{BASE_HEAD} {BASE_TREE}", "packet BASE_HEAD/tree mismatch")
    legacy_identity = _git_bytes(
        "show", "-s", "--format=%H %T", legacy.BASE_HEAD
    ).decode().strip()
    require(
        legacy_identity == f"{legacy.BASE_HEAD} {legacy.BASE_TREE}",
        "legacy ledger projection base identity mismatch",
    )
    require(
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
            check=False,
        ).returncode
        == 0,
        "checkout no longer descends from the packet base",
    )
    require(
        subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "merge-base",
                "--is-ancestor",
                PREVIOUS_RESEARCH_SOURCE,
                BASE_HEAD,
            ],
            check=False,
        ).returncode
        == 0,
        "packet previous-research source is not an ancestor of BASE_HEAD",
    )
    branch = _git_bytes("branch", "--show-current").decode().strip()
    require(branch == TASK_BRANCH, "worktree is not on the packet branch")

    input_hashes: dict[str, str] = {}
    for relative in _tracked_source_paths():
        base_data = _base_blob(relative)
        working_path = REPO_ROOT / relative
        require(working_path.is_file(), f"required source/input missing: {relative}")
        working_data = working_path.read_bytes()
        require(working_data == base_data, f"source/input differs from BASE_HEAD: {relative}")
        input_hashes[relative] = _file_sha(base_data)

    legacy_projection_inputs = (
        ROOT150_INPUT_RELATIVE,
        TS153_INPUT_RELATIVE,
        CLASSIFIED_INPUT_RELATIVE,
        STATE131_INPUT_RELATIVE,
    )
    for relative in legacy_projection_inputs:
        require(
            _legacy_blob(relative) == _base_blob(relative),
            f"112/123 ledger projection input changed since its sealed source: {relative}",
        )

    require(
        input_hashes[BASELINE_SOURCE_RELATIVE] == EXPECTED_BASELINE_SOURCE_SHA256,
        "112/123 source SHA256 mismatch",
    )
    require(
        input_hashes[BASELINE_RESULT_RELATIVE] == EXPECTED_BASELINE_RESULT_SHA256,
        "112/123 result SHA256 mismatch",
    )
    return {
        "base_head": BASE_HEAD,
        "base_tree": BASE_TREE,
        "previous_research_source": PREVIOUS_RESEARCH_SOURCE,
        "legacy_projection_head": legacy.BASE_HEAD,
        "legacy_projection_tree": legacy.BASE_TREE,
        "baseline_source": BASELINE_SOURCE_RELATIVE,
        "baseline_source_sha256": input_hashes[BASELINE_SOURCE_RELATIVE],
        "baseline_result": BASELINE_RESULT_RELATIVE,
        "baseline_result_sha256": input_hashes[BASELINE_RESULT_RELATIVE],
        "input_sha256": input_hashes,
    }


def read_base_json(relative: str) -> dict[str, Any]:
    working_data = (REPO_ROOT / relative).read_bytes()
    require(
        working_data == _base_blob(relative),
        f"JSON source differs from packet BASE_HEAD: {relative}",
    )
    return cast(dict[str, Any], json.loads(working_data))


def load_baseline_result() -> dict[str, Any]:
    return read_base_json(BASELINE_RESULT_RELATIVE)


def validate_member_max(member: dict[str, Any]) -> None:
    vector_rows = member.get("represented_vector_bounds")
    require(isinstance(vector_rows, list) and bool(vector_rows), "member lacks vector bounds")
    require(
        len(vector_rows) == int(member["represented_vector_count"]),
        "member/vector cardinality mismatch",
    )
    vector_bounds = [int(row["final_bound"]) for row in vector_rows]
    require(
        int(member["final_bound"]) == max(vector_bounds),
        f"compressed member must take MAX of represented-vector bounds: {member['member_id']}",
    )
    if "new_bound" in member:
        require(
            int(member["final_bound"]) == int(member["new_bound"]),
            f"member final_bound is stale: {member['member_id']}",
        )
    for vector_row in vector_rows:
        if "new_bound" in vector_row:
            require(
                int(vector_row["final_bound"]) == int(vector_row["new_bound"]),
                f"vector final_bound is stale: {member['member_id']}",
            )


def _baseline_terms(
    baseline: dict[str, Any], classified: dict[str, Any]
) -> tuple[tuple[str, int], ...]:
    states = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in baseline["FINAL_STATE_TERMS"]
    )
    class_terms = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in classified["FINAL_CLASSIFIED_TERMS"]
    )
    tail = (("unclassified-tail", int(classified["TAIL_BOUND"])),)
    return states + class_terms + tail


def validate_baseline_result(
    baseline: dict[str, Any],
    projection: dict[str, Any],
    classified: dict[str, Any],
) -> dict[str, Any]:
    require(
        baseline["TASK_ID"] == "B649_K20_R3_POST_H13_112_MEMBER_DUAL_CERTIFICATE_R1",
        "unexpected 112/123 result identity",
    )
    require(baseline["TASK_STATUS"] == "SUCCESS", "112/123 result is not successful")
    require(
        baseline["SOURCE_AUTHORITY_STATUS"] == "PASS_IMMUTABLE_OBJECTS_AND_LIVE_BYTES",
        "112/123 source authority was not sealed",
    )
    require(baseline["BASELINE_MEMBERS"] == 74, "112/123 predecessor count changed")
    require(baseline["BASELINE_VECTORS"] == 84, "112/123 predecessor vector count changed")
    require(baseline["NOVEL_TARGET_MEMBERS"] == 38, "112/123 novel member count changed")
    require(baseline["NOVEL_TARGET_VECTORS"] == 39, "112/123 novel vector count changed")
    require(baseline["TOTAL_ADOPTED_MEMBERS"] == 112, "112/123 member coverage changed")
    require(baseline["TOTAL_ADOPTED_VECTORS"] == 123, "112/123 vector coverage changed")
    require(
        baseline["NO_DOUBLE_COUNT_STATUS"]
        == "PASS_MAX_ALL_VALID_CREDITS_SUBTRACT_ONCE_MEMBER_MAX",
        "112/123 credit-combination semantics changed",
    )
    require(
        projection["corrections"] == baseline["BASELINE_CORRECTIONS"],
        "112/123 legacy correction membership differs from its result",
    )
    require(
        projection["total_baseline_members"] == baseline["BASELINE_MEMBERS"]
        and projection["total_baseline_vectors"] == baseline["BASELINE_VECTORS"],
        "112/123 baseline source projection counts differ",
    )
    require(
        legacy.family_digest(projection["termsbase"]) == baseline["BASELINE_TERMS_DIGEST"],
        "112/123 base family terms do not match their recorded digest",
    )

    region_member_count = 0
    region_vector_count = 0
    alias_members: dict[str, dict[str, Any]] = {}
    for region in baseline["REGIONS"]:
        members = region["complete_region_members"]
        require(len(members) == int(region["region_member_count"]), "region member ledger is incomplete")
        require(
            sum(int(member["represented_vector_count"]) for member in members)
            == int(region["region_vector_count"]),
            "region represented-vector ledger is incomplete",
        )
        member_map = {str(member["member_id"]): member for member in members}
        require(len(member_map) == len(members), "duplicate canonical member in baseline region")
        for member in members:
            validate_member_max(member)
            region_member_count += 1
            region_vector_count += int(member["represented_vector_count"])
        for member_certificate in region["member_certificates"]:
            member = member_map[str(member_certificate["member_id"])]
            require(
                int(member["final_bound"]) == int(member_certificate["new_bound"]),
                f"112/123 member effective final_bound is stale: {member['member_id']}",
            )
            for vector_certificate in member_certificate["vector_certificates"]:
                counts = vector_certificate["counts"]
                vector_row = next(
                    row for row in member["represented_vector_bounds"] if row["counts"] == counts
                )
                require(
                    int(vector_row["final_bound"]) == int(vector_certificate["new_bound"]),
                    f"112/123 vector effective final_bound is stale: {member['member_id']}",
                )
            alias_members.update(member_map)

    require(
        region_member_count == sum(int(r["region_member_count"]) for r in baseline["REGIONS"]),
        "baseline member ledger count mismatch",
    )
    require(
        region_vector_count == sum(int(r["region_vector_count"]) for r in baseline["REGIONS"]),
        "baseline vector ledger count mismatch",
    )
    aliases = baseline["COMPRESSED_ALIASES"]
    for cohort_entries in aliases.values():
        for alias in cohort_entries:
            member_id = str(alias["canonical_member_id"])
            require(member_id in alias_members, f"compressed alias missing from ledger: {member_id}")
            member = alias_members[member_id]
            require(
                member["represented_vectors"] == alias["represented_vectors"],
                f"compressed alias vectors changed: {member_id}",
            )
            require(
                member["represented_vector_count"] == len(alias["represented_vectors"]),
                f"compressed alias count changed: {member_id}",
            )
            validate_member_max(member)

    state131_rows = projection["regions"][STATE131]
    require(len(state131_rows) == 989, "State131 canonical member count changed")
    require(
        sum(int(member["represented_vector_count"]) for member in state131_rows) == 1072,
        "State131 represented-vector count changed",
    )
    for member in state131_rows:
        validate_member_max(member)
    state131_max = max(int(member["final_bound"]) for member in state131_rows)
    state131_family_bound = next(
        int(row["bound"])
        for row in baseline["FINAL_STATE_TERMS"]
        if row["stable_id"] == STATE131
    )
    require(
        state131_max == state131_family_bound == 354_981_480,
        "N1 effective final_bound reading disagrees with the 112/123 Family term",
    )
    return {
        "members": region_member_count,
        "vectors": region_vector_count,
        "compressed_aliases_sha256": legacy.digest(aliases),
        "legacy_state131_bound": state131_max,
        "baseline_family_digest": baseline["FAMILY_RECOMPUTATION"]["new_sha256"],
        "classified_term_count": len(classified["FINAL_CLASSIFIED_TERMS"]),
    }


def _vector_projection(members: list[dict[str, Any]]) -> tuple[Any, ...]:
    return tuple(
        (
            str(member["member_id"]),
            int(member["final_bound"]),
            tuple(
                (
                    tuple(tuple(int(value) for value in item) for item in row["counts"]),
                    int(row["final_bound"]),
                )
                for row in member["represented_vector_bounds"]
            ),
        )
        for member in members
    )


@cache
def build_h17_proof() -> dict[str, Any]:
    hunter = legacy.hunter
    incidences = 6 * 17
    outside_labels = 40
    quotient, remainder = divmod(incidences, outside_labels)
    collision_formula = (
        (outside_labels - remainder) * comb(quotient, 2)
        + remainder * comb(quotient + 1, 2)
    )
    collision_floor = hunter.balanced_collision_mass(incidences, outside_labels)
    require(
        hunter.type_cells(0) == (0, 0, 0, 6),
        "type-0 events must contribute six outside incidences each",
    )
    require(collision_floor == collision_formula == 84, "H17 collision floor Q is not 84")

    pair_rows = hunter.exact_pair_rows(((0, 0),))
    pair_floors = hunter.pair_floors(pair_rows)
    hunter.require_safe_pair_floors(pair_floors, pair_rows)
    require(pair_floors == FLOORS, "exact type-0 pair floors changed")
    require(
        tuple(row[6] for row in pair_rows) == FLOORS,
        "type-0 exact pair rows do not match all four floors",
    )

    minimum = hunter.minimum_tree_correction(pair_floors, collision_floor, 17)
    require(
        minimum.edge_counts == (84, 0, 0)
        and minimum.rank_floors == (13, 0, 0)
        and minimum.correction == EXPECTED_H17_CREDIT
        and minimum.census_size == 420_020,
        "complete H17 threshold minimum does not match its exact certificate",
    )
    calculated_credit = hunter.tree_weight_floor(pair_floors, minimum.rank_floors, 17)
    require(calculated_credit == minimum.correction, "H17 tree-floor formula mismatch")

    return {
        "proof_scope": "ALL_LEGAL_SUPPORTS",
        "witness_used_as_proof": False,
        "residual_event_definition": "R_i = E_i minus (E_A union E_B)",
        "core_type": 0,
        "core_vertices": 17,
        "outside_incidences": incidences,
        "outside_labels": outside_labels,
        "balanced_collision": {
            "quotient": quotient,
            "remainder": remainder,
            "floor_q": collision_floor,
            "threshold_constraint": "e1 + e2 + e3 >= Q",
        },
        "core_pair_rows": [list(row) for row in pair_rows],
        "core_pair_floors": list(pair_floors),
        "threshold_minimum": {
            "edge_counts": list(minimum.edge_counts),
            "rank_floors": list(minimum.rank_floors),
            "credit": calculated_credit,
            "cases_examined": minimum.census_size,
        },
        "core_tree_edges": 16,
        "type25_leaf": {
            "event_type": 25,
            "attach_to_core_vertex": 0,
            "leaf_edges": 1,
            "credit": 0,
            "positive_floor_applied": False,
        },
        "complete_tree": {"vertices": 18, "edges": 17, "is_tree": True},
        "pointwise_hunter_inequality": (
            "For every outcome, the tree induced by its m present residual events "
            "is a forest with at most max(m-1,0) edges; therefore "
            "1_union <= sum_i 1_R_i - sum_(i,j in T) 1_(R_i intersect R_j)."
        ),
        "universality_argument": (
            "Balanced incidence collisions force Q; exact type-0 pair floors and "
            "the nested threshold-tree/rank relaxation give the minimum core weight "
            "for every support. A zero-credit type-25 leaf completes the same tree."
        ),
    }


def verify_h17_proof(proof: dict[str, Any]) -> None:
    require(proof == build_h17_proof(), "H17 universal proof differs from exact replay")


def corrected_bound(uncorrected_bound: int, existing_credit: int, new_credit: int) -> int:
    if any(type(value) is not int for value in (uncorrected_bound, existing_credit, new_credit)):
        raise TypeError("bounds and credits must be exact integers")
    if uncorrected_bound < 0 or existing_credit < 0 or new_credit < 0:
        raise ValueError("bounds and credits must be nonnegative")
    return uncorrected_bound - max(existing_credit, new_credit)


def build_state131(
    projection: dict[str, Any], baseline: dict[str, Any], proof: dict[str, Any]
) -> dict[str, Any]:
    members = copy.deepcopy(projection["regions"][STATE131])
    require(len(members) == 989, "State131 ledger must contain all 989 members")
    require(
        sum(int(member["represented_vector_count"]) for member in members) == 1072,
        "State131 ledger must contain all 1072 represented vectors",
    )
    for member in members:
        validate_member_max(member)

    blockers = [
        member for member in members if int(member["final_bound"]) > EXPECTED_FAMILY_UB
    ]
    require(
        len(blockers) == 1 and blockers[0]["member_id"] == TARGET_MEMBER_ID,
        "State131 must have exactly the packet's unique blocking member",
    )
    target = next(member for member in members if member["member_id"] == TARGET_MEMBER_ID)
    vector_rows = target["represented_vector_bounds"]
    require(
        int(target["represented_vector_count"]) == 1 and len(vector_rows) == 1,
        "H17 target must be one canonical member and one represented vector",
    )
    vector_row = vector_rows[0]
    vector = legacy.dense(vector_row["counts"])
    require(
        vector == TARGET_VECTOR and legacy.member_id(vector) == TARGET_MEMBER_ID,
        "canonical target/member-vector identity mismatch",
    )
    require(
        vector_row["counts"] == [[0, 17], [25, 1]],
        "canonical H17 represented vector identity mismatch",
    )

    prior_bound = int(vector_row["final_bound"])
    require(prior_bound == int(target["final_bound"]), "member/vector prior bounds differ")
    uncorrected = legacy.uncorrected_bound(vector)
    existing_credit = uncorrected - prior_bound
    new_credit = int(proof["threshold_minimum"]["credit"])
    effective_credit = max(existing_credit, new_credit)
    new_bound = corrected_bound(uncorrected, existing_credit, new_credit)
    require(
        (prior_bound, uncorrected, existing_credit, new_credit, new_bound)
        == (
            EXPECTED_TARGET_PRIOR_BOUND,
            EXPECTED_TARGET_UNCORRECTED_BOUND,
            EXPECTED_EXISTING_CREDIT,
            EXPECTED_H17_CREDIT,
            EXPECTED_TARGET_NEW_BOUND,
        ),
        "State131 target arithmetic does not match the packet",
    )
    require(
        TARGET_MEMBER_ID not in projection["corrections"][STATE131],
        "new H17 target duplicates an existing correction member",
    )
    require(
        TARGET_MEMBER_ID
        not in {
            str(row["member_id"])
            for region in baseline["REGIONS"]
            for row in region["member_certificates"]
        },
        "new H17 target duplicates an existing novel 112/123 certificate",
    )

    before_preserved = _vector_projection(
        [member for member in members if member["member_id"] != TARGET_MEMBER_ID]
    )
    vector_row["new_bound"] = new_bound
    vector_row["new_core_credit"] = new_credit
    vector_row["final_bound"] = new_bound
    target["new_bound"] = new_bound
    target["new_core_credit"] = new_credit
    target["final_bound"] = new_bound
    for member in members:
        validate_member_max(member)

    after_preserved = _vector_projection(
        [member for member in members if member["member_id"] != TARGET_MEMBER_ID]
    )
    require(before_preserved == after_preserved, "a non-target State131 bound changed")
    preserved_max = max(
        int(member["final_bound"])
        for member in members
        if member["member_id"] != TARGET_MEMBER_ID
    )
    state_bound = max(int(member["final_bound"]) for member in members)
    require(
        preserved_max == EXPECTED_STATE131_UNTOUCHED_MAX
        and state_bound == EXPECTED_STATE131_UNTOUCHED_MAX,
        "State131 maximum does not equal the recomputed untouched maximum",
    )
    require(
        not [member for member in members if int(member["final_bound"]) > EXPECTED_FAMILY_UB],
        "State131 still has a blocker after the H17 correction",
    )

    return {
        "state_id": STATE131,
        "canonical_members": len(members),
        "represented_vectors": sum(int(m["represented_vector_count"]) for m in members),
        "prior_blocker_count": len(blockers),
        "prior_blocker_ids": [str(member["member_id"]) for member in blockers],
        "target_member_id": TARGET_MEMBER_ID,
        "target_vector": [[0, 17], [25, 1]],
        "target_uncorrected_bound": uncorrected,
        "target_prior_effective_bound": prior_bound,
        "target_existing_credit": existing_credit,
        "target_h17_credit": new_credit,
        "target_effective_credit": effective_credit,
        "credit_rule": "max(existing_credit, H17_credit); subtract once from uncorrected bound",
        "target_new_bound": new_bound,
        "preserved_members": len(members) - 1,
        "preserved_vectors": sum(int(m["represented_vector_count"]) for m in members) - 1,
        "preserved_remainder_max": preserved_max,
        "preserved_member_vector_bounds_sha256": legacy.digest(before_preserved),
        "preservation_check_sha256": legacy.digest(after_preserved),
        "new_state_bound": state_bound,
        "complete_region_members": members,
    }


def build_family(
    baseline: dict[str, Any],
    classified: dict[str, Any],
    state131_bound: int,
) -> dict[str, Any]:
    terms_before = _baseline_terms(baseline, classified)
    require(len(terms_before) == 56_574, "complete baseline Family needs 56,574 terms")
    require(
        len({stable_id for stable_id, _ in terms_before}) == len(terms_before),
        "duplicate Family term",
    )
    baseline_digest = legacy.family_digest(terms_before)
    baseline_max = max(bound for _, bound in terms_before)
    require(
        baseline_digest == EXPECTED_BASELINE_FAMILY_DIGEST
        == baseline["FAMILY_RECOMPUTATION"]["new_sha256"],
        "112/123 complete Family digest mismatch",
    )
    require(baseline_max == EXPECTED_TARGET_PRIOR_BOUND, "baseline Family maximum mismatch")

    matching = [i for i, (stable_id, _) in enumerate(terms_before) if stable_id == STATE131]
    require(len(matching) == 1, "State131 must occur once in the complete Family")
    index = matching[0]
    terms_after = (
        terms_before[:index]
        + ((STATE131, int(state131_bound)),)
        + terms_before[index + 1 :]
    )
    changed = sum(a != b for a, b in zip(terms_before, terms_after, strict=True))
    require(changed == 1 and terms_after[23:] == terms_before[23:], "unexpected Family term changed")
    require(len(terms_after) == 56_574, "complete Family term count changed")

    class_terms = terms_after[23:-1]
    tail = terms_after[-1]
    require(len(class_terms) == 56_550, "classified Family term count changed")
    class_digest = legacy.family_digest(class_terms)
    class_max = max(bound for _, bound in class_terms)
    require(
        class_digest == baseline["FAMILY_RECOMPUTATION"]["classified_sha256"]
        and class_max == baseline["FAMILY_RECOMPUTATION"]["classified_max"],
        "classified Family terms changed",
    )
    require(tail == ("unclassified-tail", int(classified["TAIL_BOUND"])), "Family tail changed")

    digest = legacy.family_digest(terms_after)
    ordered = sorted(terms_after, key=lambda term: (-term[1], term[0]))
    owner, runner_up = ordered[0], ordered[1]
    require(
        (digest, owner, runner_up)
        == (
            EXPECTED_FAMILY_DIGEST,
            (STATE135, EXPECTED_FAMILY_UB),
            (STATE12692531, 354_980_829),
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
        "incremental_gain": baseline_max - owner[1],
        "classified_term_count": len(class_terms),
        "classified_max": class_max,
        "classified_sha256": class_digest,
        "tail": {"stable_id": tail[0], "bound": tail[1]},
        "final_state_terms": [
            {"stable_id": stable_id, "bound": bound}
            for stable_id, bound in terms_after[:23]
        ],
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    baseline = load_baseline_result()
    classified = read_base_json(CLASSIFIED_INPUT_RELATIVE)

    # Reuse only the accepted 112/123 ledger projection. The old novel-target
    # builder, witness analysis, and Family rebuild are not invoked.
    projection = legacy.baseline_data()
    baseline_check = validate_baseline_result(baseline, projection, classified)
    proof = build_h17_proof()
    verify_h17_proof(proof)
    state131 = build_state131(projection, baseline, proof)
    family = build_family(baseline, classified, int(state131["new_state_bound"]))

    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "TASK_BRANCH": TASK_BRANCH,
        "IMPLEMENTATION_DEPTH": "NORMAL",
        "DEPTH_SOURCE": "PLANNER_SUPPLIED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "PREVIOUS_RESEARCH_SOURCE": PREVIOUS_RESEARCH_SOURCE,
        "SOURCE_AUTHORITY": authority,
        "BASELINE_112_123": {
            "source": BASELINE_SOURCE_RELATIVE,
            "source_sha256": authority["baseline_source_sha256"],
            "result": BASELINE_RESULT_RELATIVE,
            "result_sha256": authority["baseline_result_sha256"],
            "effective_final_bound_read": (
                "final_bound, checked against corrected new_bound rows and State131 Family term"
            ),
            "members": baseline["TOTAL_ADOPTED_MEMBERS"],
            "vectors": baseline["TOTAL_ADOPTED_VECTORS"],
            "new_distinct_members": 1,
            "new_distinct_vectors": 1,
            "combined_members": baseline["TOTAL_ADOPTED_MEMBERS"] + 1,
            "combined_vectors": baseline["TOTAL_ADOPTED_VECTORS"] + 1,
            "ledger_projection": baseline_check,
        },
        "COMPRESSED_ALIASES": copy.deepcopy(baseline["COMPRESSED_ALIASES"]),
        "COMPRESSED_ALIASES_SHA256": baseline_check["compressed_aliases_sha256"],
        "H17_PROOF": proof,
        "TREE_LEGALITY": "PASS_17_CORE_EDGES_PLUS_ONE_ZERO_CREDIT_TYPE25_LEAF",
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_CREDITS_SUBTRACT_ONCE",
        "STATE131": state131,
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["final_state_terms"],
        "EXPECTED_COMPLETE_FAMILY_GAIN": 105,
        "FINAL_COMPLETE_FAMILY_UB": family["final_max"],
        "FINAL_OWNER": family["owner"],
        "RUNNER_UP": family["runner_up"],
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE_DEPLOY": "NONE",
    }
    return cast(dict[str, Any], json.loads(legacy.encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    if result != build_result():
        raise AssertionError("stored result differs from source-bound deterministic replay")
    return {
        "status": "PASS",
        "state131_members": result["STATE131"]["canonical_members"],
        "state131_vectors": result["STATE131"]["represented_vectors"],
        "h17_credit": result["STATE131"]["target_h17_credit"],
        "new_state131_ub": result["STATE131"]["new_state_bound"],
        "family_ub": result["FINAL_COMPLETE_FAMILY_UB"],
        "family_digest": result["FAMILY_RECOMPUTATION"]["new_digest"],
    }


def verify_stored_result() -> dict[str, Any]:
    data = RESULT_PATH.read_bytes()
    result = cast(dict[str, Any], json.loads(data))
    summary = verify_result(result)
    if data != legacy.encode(result).encode("utf-8"):
        raise AssertionError("result bytes are not canonical")
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
        if not RESULT_PATH.parent.is_dir():
            raise FileNotFoundError(f"authorized result directory missing: {RESULT_PATH.parent}")
        payload = legacy.encode(result).encode("utf-8")
        if RESULT_PATH.exists():
            if RESULT_PATH.read_bytes() != payload:
                raise FileExistsError("refusing to replace a different result file")
        else:
            RESULT_PATH.write_bytes(payload)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "NEW_STATE131_UB": result["STATE131"]["new_state_bound"],
                "FINAL_COMPLETE_FAMILY_UB": result["FINAL_COMPLETE_FAMILY_UB"],
                "COMPLETE_FAMILY_GAIN": result["FAMILY_RECOMPUTATION"]["incremental_gain"],
                "FAMILY_DIGEST": result["FAMILY_RECOMPUTATION"]["new_digest"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
