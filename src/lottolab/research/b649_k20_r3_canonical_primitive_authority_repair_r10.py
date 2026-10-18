"""Rebuild the K20 R3 authority from the official-any-prize primitive.

R7's type vectors, residual moments, and Pareto frontier do not depend on S1.
This module pins and rechecks those inputs, then recomputes every frontier and
tail bound with the canonical single-ticket count.  The seven R9 state
certificates are reused only after source, witness, outcome, and histogram
checks; they are refinements, not the complete corrected frontier.
"""

from __future__ import annotations

import json
from functools import cache
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any

from lottolab.research import (
    b649_k20_outside_min_s2_global_penalty_bound_r1 as r1,
)
from lottolab.research import (
    b649_k20_r3_anchor_incidence_bound_r5 as r5,
)
from lottolab.research import (
    b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6,
)
from lottolab.research import (
    b649_k20_r3_frontier_realizability_bound_r8 as r8,
)
from lottolab.research import (
    b649_k20_r3_joint_residual_envelope_r7 as r7,
)

TASK_ID = "B649_K20_R3_CANONICAL_PRIMITIVE_AUTHORITY_REPAIR_R10"
BASE_HEAD = "862b61c9bccc25222d17b664a77bdaf5014e77a1"
BASE_TREE = "68cbefac9a215df49e9825d422bc32b2dfcc16d5"
TASK_BRANCH = "codex/b649-k20-r3-canonical-primitive-authority-repair-r10"
R4_REFERENCE_BOUND = 350_545_749
R9_CANONICAL_TAIL_CEILING = 358_352_829
RESULT_PATH = (
    Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results/"
    "b649-k20-r3-canonical-primitive-authority-repair-r10-result.json"
)
R7_RESULT_PATH = (
    Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results/"
    "b649-k20-r3-joint-residual-envelope-r7-result.json"
)
R8_RESULT_PATH = (
    Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results/"
    "b649-k20-r3-frontier-realizability-bound-r8-result.json"
)
R9_RESULT_PATH = (
    Path(__file__).resolve().parents[3] / "docs/research/matrix-native-results/"
    "b649-k20-r3-seven-state-higher-order-bound-r9-result.json"
)

# These hashes pin the S1-independent structures and the already-produced
# R8/R9 evidence to the exact R10 base tree.  A mismatch invalidates reuse.
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_outside_min_s2_global_penalty_bound_r1.py": (
        "7706e57e77df6e786e77c4824f3c72663fdae73b20aa5f6797192689f2b6ea62"
    ),
    "src/lottolab/research/b649_k20_r3_anchor_incidence_bound_r5.py": (
        "569d525f1e9905d043fe0f6132c936d5b260ba3d4b3a376da6c961db8aa5c435"
    ),
    "src/lottolab/research/b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py": (
        "a83f6f2a7091aedf034e0905d80993df5001382fedc297fdd503202665e6622c"
    ),
    "src/lottolab/research/b649_k20_r3_joint_residual_envelope_r7.py": (
        "f376899a25bc287e45b80c3f5d9116db97f4c09de31ec81d0ccd2badf4222c50"
    ),
    "src/lottolab/research/b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
    "src/lottolab/research/b649_k20_r3_seven_state_higher_order_bound_r9.py": (
        "53819d16316567cd2bcc5bb6f4ae45ef7d839b5d392fb2f1d712f7a6c8a19f15"
    ),
    "src/lottolab/research/b649_k20_r3_seven_state_higher_order_bound_r9.cpp": (
        "acd00c6e2ed3f8a00c2ae05ef15a6833262478bf56115fcf116e356f6b805ff6"
    ),
    "src/lottolab/research/b649_official_any_prize_exact.py": (
        "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-joint-residual-envelope-r7-result.json": (
        "463f0e1d577e5e175822d7fc52b1237fd7eb750fbd8ac654280993c160051f02"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-frontier-realizability-bound-r8-result.json": (
        "63ecd6b76fef541795d6b6956fd25592fd35e8f7f172fc722156a6b7bcfe0e71"
    ),
    (
        "docs/research/matrix-native-results/"
        "b649-k20-r3-seven-state-higher-order-bound-r9-result.json"
    ): ("9136d9c4d9487a999719e570da65d528f5d9f8e7e210de707feb0de418d93465"),
}


def canonical_primitives() -> dict[str, int]:
    """Return exact counts from the official seven-number outcome model."""

    pool_size = r1.POOL_SIZE
    draw_size = r1.DRAW_SIZE
    special_choices = pool_size - draw_size
    outcome_space = comb(pool_size, draw_size) * special_choices
    seven_set_outcomes = comb(pool_size, draw_size + 1) * (draw_size + 1)
    if outcome_space != seven_set_outcomes:
        raise AssertionError("the main/special and seven-set outcome spaces disagree")

    # Each unordered seven-label set represents seven main/special outcomes.
    # A ticket wins exactly when it shares at least three labels with that set.
    single_ticket = (draw_size + 1) * sum(
        comb(draw_size, hits) * comb(pool_size - draw_size, draw_size + 1 - hits)
        for hits in range(r1.OUTRIGHT_MATCHES, draw_size + 1)
    )
    diagonal_i6 = r1.pair_intersection_count(draw_size)
    k20_s1 = r1.TICKET_COUNT * single_ticket
    legacy_single = r1.SINGLE_TICKET_OUTCOMES
    legacy_k20_s1 = r1.PORTFOLIO_S1
    correction = k20_s1 - legacy_k20_s1

    if outcome_space != 601_304_088:
        raise AssertionError("official-any-prize outcome-space identity changed")
    if single_ticket != 18_611_432 or diagonal_i6 != single_ticket:
        raise AssertionError("canonical single-ticket count disagrees with pair diagonal I6")
    if k20_s1 != 372_228_640 or correction != 7_807_080:
        raise AssertionError("canonical K20 S1 correction failed")
    return {
        "OFFICIAL_ANY_PRIZE_OUTCOME_SPACE": outcome_space,
        "SINGLE_TICKET_ANY_PRIZE": single_ticket,
        "PAIR_DIAGONAL_I6": diagonal_i6,
        "K20_S1": k20_s1,
        "OLD_INVALID_SINGLE_TICKET_COUNT": legacy_single,
        "OLD_INVALID_K20_S1": legacy_k20_s1,
        "S1_CORRECTION": correction,
    }


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_upstream_fingerprints() -> dict[str, str]:
    """Fail closed if any reused module or stored certificate has drifted."""

    repo_root = Path(__file__).resolve().parents[3]
    observed = {relative: _sha256(repo_root / relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        mismatches = {
            path: {"expected": UPSTREAM_SHA256[path], "observed": observed[path]}
            for path in UPSTREAM_SHA256
            if observed[path] != UPSTREAM_SHA256[path]
        }
        raise AssertionError(f"R7/R8/R9 evidence fingerprint mismatch: {mismatches}")
    return observed


def _point_digest(points: tuple[Any, ...]) -> str:
    payload = "\n".join(f"{point.joint_s2},{point.maximum_joint_s3}" for point in points)
    return sha256(payload.encode("ascii")).hexdigest()


def _sparse_counts(counts: tuple[int, ...]) -> list[list[int]]:
    return [[index, count] for index, count in enumerate(counts) if count]


def _state_identifier(joint_s2: int, maximum_joint_s3: int) -> str:
    return f"s2-{joint_s2}-s3-{maximum_joint_s3}"


def _moment(histogram: list[int], order: int) -> int:
    return sum(comb(multiplicity, order) * count for multiplicity, count in enumerate(histogram))


def _verify_r7_census(
    census: r7.JointResidualCensus, r7_result: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    """Check all S1-independent R7 vector, residual, and frontier fingerprints."""

    frontier_rows = tuple(
        (int(row["JOINT_S2"]), int(row["MAXIMUM_JOINT_S3"])) for row in r7_result["S2_S3_FRONTIER"]
    )
    computed_rows = tuple((point.joint_s2, point.maximum_joint_s3) for point in census.frontier)
    if computed_rows != frontier_rows:
        raise AssertionError("the recomputed R7 S2/S3 frontier differs from its certificate")

    checks = {
        "REUSED_EXACT_TYPE_COUNT_VECTOR_COUNT": census.reused_vector_count,
        "REUSED_EXACT_TYPE_COUNT_VECTOR_SHA256_REPR": census.reused_vector_sha256,
        "CANDIDATE_TYPE_COUNT_VECTOR_COUNT": census.candidate_vector_count,
        "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": census.feasible_vector_count,
        "FEASIBLE_REUSED_TYPE_COUNT_VECTOR_COUNT": census.feasible_reused_vector_count,
        "FEASIBLE_SUPPLEMENTAL_TYPE_COUNT_VECTOR_COUNT": (
            census.feasible_supplemental_vector_count
        ),
        "RESIDUAL_STATE_COUNT": len(census.states),
        "S2_LEVEL_COUNT": census.s2_level_count,
        "S2_S3_ENVELOPE_LEVEL_COUNT": len(census.s2_s3_envelope),
        "S2_S3_ENVELOPE_SHA256": _point_digest(census.s2_s3_envelope),
        "S2_S3_FRONTIER_SIZE": len(census.frontier),
        "S2_S3_FRONTIER_SHA256": _point_digest(census.frontier),
    }
    for key, value in checks.items():
        if r7_result.get(key) != value:
            raise AssertionError(f"R7 fingerprint/count mismatch for {key}")
    return tuple(
        {
            "state_id": _state_identifier(point.joint_s2, point.maximum_joint_s3),
            "joint_s2": point.joint_s2,
            "maximum_joint_s3": point.maximum_joint_s3,
            "witness_counts_sparse": _sparse_counts(point.witness_counts),
        }
        for point in census.frontier
    )


def _verify_r9_refinements(
    primitives: dict[str, int],
    frontier: tuple[dict[str, Any], ...],
    r8_result: dict[str, Any],
    r9_result: dict[str, Any],
    joint_constant: int,
) -> dict[str, dict[str, Any]]:
    """Validate the seven structurally overlapping R9 refinements."""

    frontier_by_id = {str(row["state_id"]): row for row in frontier}
    r8_rows = {str(row["state_id"]): row for row in r8_result["R3_LOAD_BEARING_FRONTIER_STATES"]}
    r9_rows = r9_result["R3_LOAD_BEARING_STATES"]
    expected_ids = tuple(r8.SUPPORT_WITNESS_BITMASKS)
    if tuple(row["state_id"] for row in r9_rows) != expected_ids:
        raise AssertionError("R9 state order/identity differs from the pinned R8 witnesses")

    profiles = r5.anchor_incidence_profiles()
    refinements: dict[str, dict[str, Any]] = {}
    for row in r9_rows:
        state_id = str(row["state_id"])
        point = frontier_by_id.get(state_id)
        prior = r8_rows.get(state_id)
        if point is None or prior is None:
            raise AssertionError("an R9 refinement is outside the corrected R3 frontier")
        if row["witness_counts_sparse"] != point["witness_counts_sparse"]:
            raise AssertionError("R9 count vector differs from its fingerprinted R7 point")

        bitmasks = tuple(int(mask) for mask in row["support_witness_bitmasks"])
        if bitmasks != r8.SUPPORT_WITNESS_BITMASKS[state_id]:
            raise AssertionError("R9 support witness differs from the frozen R8 copy")
        witness = r8.decode_support_witness_bitmasks(bitmasks)
        witness_digest = sha256(repr(witness).encode("ascii")).hexdigest()
        if witness_digest != row["support_witness_sha256"]:
            raise AssertionError("R9 support witness fingerprint mismatch")
        if prior["s4_support_witness_sha256"] != witness_digest:
            raise AssertionError("R8 and R9 support witness fingerprints disagree")

        counts = tuple(
            sum(count for index, count in row["witness_counts_sparse"] if index == slot)
            for slot in range(len(profiles))
        )
        anchor_s2 = sum(
            count * profile.pair_recovery_cost
            for count, profile in zip(counts, profiles, strict=True)
        )
        anchor_s3 = sum(
            count * profile.triple_recovery for count, profile in zip(counts, profiles, strict=True)
        )
        if (anchor_s2, anchor_s3) != (row["anchor_s2"], row["anchor_s3"]):
            raise AssertionError("R9 exact anchor S2/S3 values differ from the R7 vector")

        exact_s1 = (r1.TICKET_COUNT - 2) * primitives["SINGLE_TICKET_ANY_PRIZE"]
        exact_s1 -= anchor_s2
        exact_s1 += anchor_s3
        if exact_s1 != row["residual_s1_exact"]:
            raise AssertionError("R9 residual S1 was not computed from canonical single S1")

        witness_hist = row["witness_exact_histogram"]
        full_hist = [int(value) for value in witness_hist["full_portfolio_histogram"]]
        exclusive_hist = [
            int(value) for value in witness_hist["anchor_exclusive_residual_histogram"]
        ]
        if sum(full_hist) != primitives["OFFICIAL_ANY_PRIZE_OUTCOME_SPACE"]:
            raise AssertionError("R9 exact witness histogram does not conserve outcomes")
        if _moment(exclusive_hist, 1) != exact_s1:
            raise AssertionError("R9 exact witness histogram has the wrong canonical S1")
        if _moment(exclusive_hist, 2) < row["residual_s2_certified_lower_bound"]:
            raise AssertionError("R9 exact witness histogram violates its certified S2 floor")

        envelope = row["state_wide_joint_histogram_envelope"]
        if envelope["status"] != "OPTIMAL":
            raise AssertionError("R9 histogram relaxation lacks an optimality certificate")
        relaxed = envelope.get("histogram")
        if relaxed is None:
            raise AssertionError("R9 optimal histogram relaxation omitted its histogram")
        relaxed_hist = [int(value) for value in relaxed]
        correction = sum(
            (multiplicity - 1) * count
            for multiplicity, count in enumerate(relaxed_hist)
            if multiplicity >= 2
        )
        if (
            sum(relaxed_hist) != envelope["outcome_count"]
            or _moment(relaxed_hist, 1) != exact_s1
            or _moment(relaxed_hist, 2) < envelope["s2_lower_bound"]
            or correction != envelope["certified_correction_lower_bound"]
            or correction != envelope["incumbent_correction"]
        ):
            raise AssertionError("R9 joint histogram moments/correction failed recomputation")

        certified_bound = joint_constant - anchor_s2 + anchor_s3 - correction
        if certified_bound != row["certified_state_r3_bound"]:
            raise AssertionError("R9 state bound does not match the canonical primitive formula")
        if (
            r9_result["UPSTREAM_ARITHMETIC_AUDIT"]["exact_single_ticket_outcomes"]
            != primitives["SINGLE_TICKET_ANY_PRIZE"]
            or r9_result["UPSTREAM_ARITHMETIC_AUDIT"]["exact_diagonal_pair_intersection"]
            != primitives["PAIR_DIAGONAL_I6"]
        ):
            raise AssertionError("R9 arithmetic audit does not match the canonical primitive")

        cap = row["maximum_residual_winning_multiplicity"]
        structural_cap = r1.TICKET_COUNT - 2
        if cap.get("class_certified_upper_bound") != structural_cap:
            raise AssertionError("R9 multiplicity cap differs from the 18-ticket structural cap")
        if cap.get("status") == "OPTIMAL":
            if cap.get("exact_maximum") != structural_cap:
                raise AssertionError("R9 optimal multiplicity result differs from its class cap")
        elif cap.get("status") == "FEASIBLE":
            if (
                cap.get("exact_maximum") is not None
                or cap.get("certified_upper_bound") != structural_cap
                or cap.get("objective_bound") != float(structural_cap)
            ):
                raise AssertionError("R9 FEASIBLE multiplicity record lacks its safe bound")
        else:
            raise AssertionError("R9 multiplicity record has an unrecognized solver status")

        refinements[state_id] = {
            "certified_state_r3_bound": certified_bound,
            "histogram_correction_lower_bound": correction,
            "histogram_solver_status": envelope["status"],
            "multiplicity_cap": cap["class_certified_upper_bound"],
            "multiplicity_solver_status": cap["status"],
            "multiplicity_exactness_source": cap["exactness_source"],
            "multiplicity_bound_source": "STRUCTURAL_MAXIMUM_FROM_18_RESIDUAL_TICKETS",
            "support_witness_sha256": witness_digest,
            "s4_minimum_certified_lower_bound": prior["s4_minimum_certified_lower_bound"],
            "s4_minimum_proven": bool(prior["s4_minimum_proven"]),
        }

    if len(refinements) != 7:
        raise AssertionError("the reused R9 evidence must contain seven refinements")
    if sum(not row["s4_minimum_proven"] for row in refinements.values()) != 1:
        raise AssertionError("R8/R9 S4 proof-status boundary changed")
    return refinements


@cache
def build_canonical_authority_result() -> dict[str, Any]:
    """Recompute the complete corrected frontier, tail, and final R3 bound."""

    fingerprints = verify_upstream_fingerprints()
    primitives = canonical_primitives()
    r7_result = json.loads(R7_RESULT_PATH.read_text(encoding="utf-8"))
    r8_result = json.loads(R8_RESULT_PATH.read_text(encoding="utf-8"))
    r9_result = json.loads(R9_RESULT_PATH.read_text(encoding="utf-8"))
    census = r7.joint_residual_census()
    frontier = _verify_r7_census(census, r7_result)

    anchor_pair_intersection = r1.pair_intersection_count(r1.OUTRIGHT_MATCHES)
    if anchor_pair_intersection != r7.ANCHOR_PAIR_INTERSECTION:
        raise AssertionError("S1-independent anchor-pair intersection changed")
    joint_constant = primitives["K20_S1"] - anchor_pair_intersection
    if joint_constant != r9_result["UPSTREAM_ARITHMETIC_AUDIT"]["exact_joint_expression_constant"]:
        raise AssertionError("canonical joint-expression constant failed R9 cross-check")

    refinements = _verify_r9_refinements(primitives, frontier, r8_result, r9_result, joint_constant)
    r4_selected = tuple(
        row
        for row in frontier
        if joint_constant - row["joint_s2"] + row["maximum_joint_s3"] > R4_REFERENCE_BOUND
    )
    if len(r4_selected) != 23:
        raise AssertionError("the corrected R4-threshold frontier is not the complete 23 states")

    corrected_frontier: list[dict[str, Any]] = []
    for row in r4_selected:
        raw_bound = joint_constant - row["joint_s2"] + row["maximum_joint_s3"]
        refinement = refinements.get(row["state_id"])
        state_bound = (
            int(refinement["certified_state_r3_bound"]) if refinement is not None else raw_bound
        )
        corrected_frontier.append(
            {
                "state_id": row["state_id"],
                "joint_s2": row["joint_s2"],
                "maximum_joint_s3": row["maximum_joint_s3"],
                "canonical_frontier_upper_bound": raw_bound,
                "capable_of_exceeding_r4_reference": raw_bound > R4_REFERENCE_BOUND,
                "refinement_source": (
                    "R9_OPTIMAL_HISTOGRAM_AND_MULTIPLICITY"
                    if refinement is not None
                    else "R7_EXACT_S2_S3_FRONTIER"
                ),
                "certified_state_r3_upper_bound": state_bound,
            }
        )
    corrected_frontier.sort(
        key=lambda row: (-row["canonical_frontier_upper_bound"], row["state_id"])
    )
    for rank, row in enumerate(corrected_frontier, start=1):
        row["canonical_frontier_rank"] = rank

    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    cutoff = r7.JOINT_LOCAL_LOSS_CUTOFF
    next_threshold_vectors = tuple(
        r6.iter_type_count_vectors(losses, r1.TICKET_COUNT - 2, cutoff + 1)
    )
    at_cutoff_plus_one = sum(
        sum(count * loss for count, loss in zip(vector, losses, strict=True)) == cutoff + 1
        for vector in next_threshold_vectors
    )
    if len(next_threshold_vectors) != census.candidate_vector_count:
        raise AssertionError("the cutoff+1 census changed the exact candidate-vector count")

    # R6's baseline contains a fixed, S1-independent reduction.  Recover that
    # fixed term, then replace only its old portfolio S1 with canonical K20 S1.
    fixed_baseline_reduction = r1.PORTFOLIO_S1 - r6.UNCORRECTED_R3_BOUND
    if fixed_baseline_reduction != 7_180_012:
        raise AssertionError("the fingerprinted R6 fixed baseline reduction changed")
    canonical_uncorrected_baseline = primitives["K20_S1"] - fixed_baseline_reduction
    minimum_omitted_loss = cutoff + (2 if at_cutoff_plus_one == 0 else 1)
    tail_bound = canonical_uncorrected_baseline - minimum_omitted_loss

    r3_bound = max(
        tail_bound,
        *(int(row["certified_state_r3_upper_bound"]) for row in corrected_frontier),
    )
    if r3_bound != 358_352_828:
        raise AssertionError("the corrected R3 formula did not produce the certified bound")
    if r3_bound >= R9_CANONICAL_TAIL_CEILING:
        raise AssertionError("the corrected R3 bound failed the strict canonical-tail target")

    incumbent = r1.INCUMBENT
    family_bound = max(r3_bound, R4_REFERENCE_BOUND)
    s4_status = r9_result["EXACT_S4_STATUS"]
    s4_summary = {
        "first_six_exact_minima": s4_status["first_six_exact_minima"],
        "last_state_id": s4_status["last_state_id"],
        "last_state_minimum_interval": s4_status["last_state_minimum_interval"],
        "last_state_minimum_proven": s4_status["last_state_minimum_proven"],
        "last_state_solver_status": s4_status["last_state_solver"]["status"],
        "last_state_native_wall_limit_seconds": s4_status["last_state_solver"][
            "native_wall_limit_seconds"
        ],
        "last_state_external_timeout_seconds": s4_status["last_state_solver"][
            "external_timeout_seconds"
        ],
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_CORRECTED_R3_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "CANONICAL_SINGLE_TICKET_COUNT": primitives["SINGLE_TICKET_ANY_PRIZE"],
        "PAIR_DIAGONAL_I6": primitives["PAIR_DIAGONAL_I6"],
        "K20_S1": primitives["K20_S1"],
        "OLD_INVALID_SINGLE_TICKET_COUNT": primitives["OLD_INVALID_SINGLE_TICKET_COUNT"],
        "S1_CORRECTION": primitives["S1_CORRECTION"],
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "S1_INDEPENDENT_R7_CENSUS": {
            "REUSED_EXACT_TYPE_COUNT_VECTOR_COUNT": census.reused_vector_count,
            "REUSED_EXACT_TYPE_COUNT_VECTOR_SHA256_REPR": census.reused_vector_sha256,
            "CANDIDATE_TYPE_COUNT_VECTOR_COUNT": census.candidate_vector_count,
            "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": census.feasible_vector_count,
            "RESIDUAL_STATE_COUNT": len(census.states),
            "S2_LEVEL_COUNT": census.s2_level_count,
            "S2_S3_ENVELOPE_SHA256": _point_digest(census.s2_s3_envelope),
            "S2_S3_FRONTIER_SHA256": _point_digest(census.frontier),
            "S2_S3_FRONTIER_SIZE": len(census.frontier),
        },
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "CORRECTED_LOAD_BEARING_STATE_COUNT": len(corrected_frontier),
        "CORRECTED_LOAD_BEARING_FRONTIER": corrected_frontier,
        "REUSED_R9_REFINEMENTS": refinements,
        "REUSED_R9_EXACT_S4_SUMMARY": s4_summary,
        "TAIL_CERTIFICATE": {
            "LOCAL_LOSS_CUTOFF": cutoff,
            "CANDIDATE_VECTOR_COUNT_AT_CUTOFF_PLUS_ONE": len(next_threshold_vectors),
            "VECTORS_AT_EXACT_CUTOFF_PLUS_ONE": at_cutoff_plus_one,
            "MINIMUM_OMITTED_LOCAL_LOSS": minimum_omitted_loss,
            "FIXED_BASELINE_REDUCTION_INDEPENDENT_OF_S1": fixed_baseline_reduction,
            "CANONICAL_UNCORRECTED_BASELINE": canonical_uncorrected_baseline,
            "CORRECTED_TAIL_BOUND": tail_bound,
            "R9_PREVIOUS_CANONICAL_TAIL_BOUND": R9_CANONICAL_TAIL_CEILING,
        },
        "R3_BOUND_FORMULA": (
            "max(CANONICAL_K20_S1 - fixed_R6_baseline_reduction - "
            "minimum_omitted_local_loss, all 23 canonical frontier terms; "
            "use verified R9 state-wide histogram bounds for its seven overlapping states)"
        ),
        "R3_BOUND": r3_bound,
        "R3_STATUS": "CERTIFIED_STRICTLY_BELOW_R9_CANONICAL_TAIL",
        "SUCCESS_A": r3_bound <= R4_REFERENCE_BOUND,
        "SUCCESS_B": r3_bound < R9_CANONICAL_TAIL_CEILING,
        "SUCCESS_C": len(corrected_frontier) == 23 and r3_bound == tail_bound,
        "FAMILY_A_RECOMPUTED_BOUND": family_bound,
        "FAMILY_A_BOTTLENECK_R": "R3" if r3_bound >= R4_REFERENCE_BOUND else "R4",
        "INCUMBENT": incumbent,
        "REMAINING_GAP": family_bound - incumbent,
        "FOCUSED_TESTS": "NOT_RUN",
        "RUFF": "NOT_RUN",
        "PYRIGHT": "NOT_RUN",
        "SOLVER_EXECUTION": {
            "NEW_SOLVER_RUNS": "NONE; fingerprinted R9 optimal certificates reused",
            "CURRENT_RUNTIME_PREFLIGHT": (
                "BLOCKED: active Python 3.13 environment has no OR-Tools package"
            ),
            "REUSED_R9_RUNTIME_PREFLIGHT": r9_result["SOLVER_RUNTIME_PREFLIGHT"],
            "FEASIBLE_IS_PROOF": False,
            "S4_UNPROVEN_STATE": r9_result["EXACT_S4_STATUS"]["last_state_id"],
            "S4_UNPROVEN_STATE_USED_AS_PROOF": False,
        },
        "ATTEMPT_LEDGER": [
            {
                "attempt": 1,
                "action": "Import standalone official-any-prize evaluator",
                "result": "BLOCKED",
                "reason": "NumPy is unavailable in the active Python 3.13 runtime",
                "state_change": "NONE",
            },
            {
                "attempt": 2,
                "action": "R9 solver runtime preflight in active Python 3.13 runtime",
                "result": "BLOCKED",
                "reason": "OR-Tools is unavailable; no new solver was launched",
                "state_change": "NONE",
            },
            {
                "attempt": 3,
                "action": "Reuse R9 exact certificates after pinned fingerprint checks",
                "result": "PASS",
                "reason": (
                    "All seven histogram relaxations are OPTIMAL; multiplicity uses "
                    "optimal or conservative structural caps"
                ),
                "state_change": "NONE",
            },
            {
                "attempt": 4,
                "action": "Build pre-commit R10 result record",
                "result": "FAILED_THEN_REPAIRED",
                "reason": (
                    "R7 frontier point exposes coordinates rather than an identifier property"
                ),
                "state_change": "NONE",
            },
            {
                "attempt": 5,
                "action": "Build pre-commit R10 result record",
                "result": "FAILED_THEN_REPAIRED",
                "reason": "R8 result names the witness digest s4_support_witness_sha256",
                "state_change": "NONE",
            },
            {
                "attempt": 6,
                "action": "Build pre-commit R10 result record",
                "result": "FAILED_THEN_REPAIRED",
                "reason": (
                    "One R9 FEASIBLE multiplicity status requires conservative interpretation"
                ),
                "state_change": "NONE",
            },
            {
                "attempt": 7,
                "action": "Initial focused Ruff/Pyright checks",
                "result": "FAILED_THEN_REPAIRED",
                "reason": "Import order, formatting, and inferred list type needed correction",
                "state_change": "NONE",
            },
            {
                "attempt": 8,
                "action": "Focused Ruff import check",
                "result": "FAILED_THEN_REPAIRED",
                "reason": "Ruff project rules require separate from-import blocks",
                "state_change": "NONE",
            },
        ],
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def write_result(
    path: Path = RESULT_PATH,
    *,
    focused_tests: str = "NOT_RUN",
    ruff: str = "NOT_RUN",
    pyright: str = "NOT_RUN",
) -> None:
    """Write the compact machine-readable certificate into the task worktree."""

    result = dict(build_canonical_authority_result())
    result["FOCUSED_TESTS"] = focused_tests
    result["RUFF"] = ruff
    result["PYRIGHT"] = pyright
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    write_result()
    print(json.dumps(build_canonical_authority_result(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BASE_HEAD",
    "BASE_TREE",
    "R4_REFERENCE_BOUND",
    "RESULT_PATH",
    "TASK_BRANCH",
    "TASK_ID",
    "build_canonical_authority_result",
    "canonical_primitives",
    "verify_upstream_fingerprints",
    "write_result",
]
