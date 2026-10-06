"""Identify and tighten the unique load-bearing K20 R3 bound term."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, cast

from lottolab.research import (
    b649_k20_outside_min_s2_global_penalty_bound_r1 as r1,
)
from lottolab.research import (
    b649_k20_r3_anchor_incidence_bound_r5 as r5,
)
from lottolab.research import (
    b649_k20_r3_canonical_primitive_authority_repair_r10 as r10,
)
from lottolab.research import (
    b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6,
)
from lottolab.research import (
    b649_k20_r3_joint_residual_envelope_r7 as r7,
)

TASK_ID = "B649_K20_R3_CORRECTED_BOUND_OWNER_REDUCTION_R11"
BASE_HEAD = "b662fe93f2eeb3cac95163b85f82c92dff763ef3"
BASE_TREE = "29a0b83293c326073b313e334533e3ca4647c226"
TASK_BRANCH = "codex/b649-k20-r3-corrected-bound-owner-reduction-r11"
PRIOR_R3_BOUND = 358_352_828
R4_REFERENCE_BOUND = 350_545_749
PRIOR_TAIL_RELAXATION_CUTOFF = 6_695_798
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    REPO_ROOT
    / "docs/research/matrix-native-results/b649-k20-r3-bound-owner-reduction-r11-result.json"
)
PRIOR_RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-canonical-primitive-authority-repair-r10-result.json"
)


@dataclass(frozen=True)
class BoundTerm:
    """A stable top-level term in the certified R3 maximum."""

    term_id: str
    bound: int
    primitive_dependencies: tuple[str, ...]
    structural_certificate_source: str
    prior_uncorrected_frontier_bound: int | None = None


def identify_owner_set(terms: Iterable[BoundTerm]) -> tuple[str, ...]:
    """Return every term tied at the maximum, preserving stable input order."""

    rows = tuple(terms)
    if not rows:
        raise ValueError("at least one R3 term is required")
    identifiers = tuple(row.term_id for row in rows)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("R3 term identifiers must be unique")
    maximum = max(row.bound for row in rows)
    return tuple(row.term_id for row in rows if row.bound == maximum)


def _required_int(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    if type(value) is not int:
        raise AssertionError(f"{key} must be an integer certificate field")
    return value


@cache
def _prior_result() -> dict[str, Any]:
    """Load the pinned R10 result after checking its exact input fingerprints."""

    r10.verify_upstream_fingerprints()
    record: dict[str, Any] = json.loads(PRIOR_RESULT_PATH.read_text(encoding="utf-8"))
    if record.get("TASK_STATUS") != "CERTIFIED_CORRECTED_R3_BOUND_TIGHTENED":
        raise AssertionError("the pinned R10 certificate is not in its certified state")
    if record.get("R3_BOUND") != PRIOR_R3_BOUND:
        raise AssertionError("the pinned R10 R3 bound differs from the task authority")
    if record.get("BASE_HEAD") != r10.BASE_HEAD or record.get("BASE_TREE") != r10.BASE_TREE:
        raise AssertionError("the pinned R10 result has an unexpected source identity")
    return record


def canonical_primitives() -> dict[str, int]:
    """Recheck the official-any-prize primitives used by every R3 term."""

    primitives = r10.canonical_primitives()
    if primitives["SINGLE_TICKET_ANY_PRIZE"] != 18_611_432:
        raise AssertionError("canonical single-ticket any-prize count changed")
    if primitives["PAIR_DIAGONAL_I6"] != 18_611_432:
        raise AssertionError("canonical pair-intersection diagonal changed")
    if primitives["K20_S1"] != 372_228_640:
        raise AssertionError("canonical K20 S1 changed")
    return primitives


def top_level_terms() -> tuple[BoundTerm, ...]:
    """Project the corrected tail and 23 certified state terms without reruns."""

    record = _prior_result()
    tail = record["TAIL_CERTIFICATE"]
    terms = [
        BoundTerm(
            term_id="corrected-tail",
            bound=_required_int(tail, "CORRECTED_TAIL_BOUND"),
            primitive_dependencies=(
                "CANONICAL_K20_S1",
                "R6_FIXED_BASELINE_REDUCTION",
                "R7_JOINT_LOCAL_LOSS_CUTOFF",
                "EXACT_30_PROFILE_18_TICKET_COUNT_VECTOR_SPECTRUM",
            ),
            structural_certificate_source=(
                "R10_TAIL_CERTIFICATE: integer local-loss cutoff; exact R11 "
                "count-vector census tightens its omitted-loss floor"
            ),
        )
    ]
    raw_rows: object = record["CORRECTED_LOAD_BEARING_FRONTIER"]
    if not isinstance(raw_rows, list):
        raise AssertionError("the corrected R10 frontier is not a state list")
    rows = cast(list[object], raw_rows)
    if len(rows) != 23:
        raise AssertionError("the corrected R10 frontier must contain 23 states")
    typed_rows: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise AssertionError("the corrected R10 frontier contains a malformed state")
        typed_rows.append(cast(dict[str, Any], raw_row))
    raw_refinements: object = record["REUSED_R9_REFINEMENTS"]
    if not isinstance(raw_refinements, dict):
        raise AssertionError("the corrected R10 certificate omitted its R9 refinements")
    refinements = cast(dict[str, dict[str, Any]], raw_refinements)
    for row in typed_rows:
        state_id = str(row["state_id"])
        source = str(row["refinement_source"])
        raw_bound = _required_int(row, "canonical_frontier_upper_bound")
        state_bound = _required_int(row, "certified_state_r3_upper_bound")
        if source == "R9_OPTIMAL_HISTOGRAM_AND_MULTIPLICITY":
            refinement = refinements.get(state_id)
            if not isinstance(refinement, dict):
                raise AssertionError(f"the R9 source record for {state_id} is absent")
            if refinement.get("histogram_solver_status") != "OPTIMAL":
                raise AssertionError(f"the R9 histogram source for {state_id} is not optimal")
            if refinement.get("multiplicity_bound_source") != (
                "STRUCTURAL_MAXIMUM_FROM_18_RESIDUAL_TICKETS"
            ):
                raise AssertionError(f"the R9 multiplicity source for {state_id} changed")
            detail = (
                "R9_OPTIMAL_HISTOGRAM_AND_MULTIPLICITY; "
                f"histogram correction={refinement['histogram_correction_lower_bound']}; "
                "multiplicity cap=18 from residual-ticket structure; "
                f"support witness SHA256={refinement['support_witness_sha256']}"
            )
            dependencies = (
                "CANONICAL_K20_S1",
                "ANCHOR_PAIR_INTERSECTION_I3",
                "EXACT_ANCHOR_S2_AND_S3",
                "R9_OPTIMAL_JOINT_HISTOGRAM_CORRECTION",
                "18_RESIDUAL_TICKET_MULTIPLICITY_CAP",
            )
        elif source == "R7_EXACT_S2_S3_FRONTIER":
            detail = "R7_EXACT_S2_S3_FRONTIER; coherent frontier point from one type-count state"
            dependencies = (
                "CANONICAL_K20_S1",
                "ANCHOR_PAIR_INTERSECTION_I3",
                "JOINT_S2",
                "MAXIMUM_JOINT_S3",
            )
        else:
            raise AssertionError(f"unknown structural certificate source for {state_id}")
        terms.append(
            BoundTerm(
                term_id=f"state:{state_id}",
                bound=state_bound,
                primitive_dependencies=dependencies,
                structural_certificate_source=detail,
                prior_uncorrected_frontier_bound=raw_bound,
            )
        )
    if len(terms) != 24:
        raise AssertionError("top-level R3 must contain the tail and exactly 23 states")
    return tuple(terms)


@cache
def exact_tail_spectrum() -> dict[str, Any]:
    """Count type vectors through cutoff+2 and certify the next omitted loss."""

    started = time.monotonic()
    record = _prior_result()
    census = record["S1_INDEPENDENT_R7_CENSUS"]
    tail_certificate = record["TAIL_CERTIFICATE"]
    candidate_count = _required_int(census, "CANDIDATE_TYPE_COUNT_VECTOR_COUNT")
    cutoff = r7.JOINT_LOCAL_LOSS_CUTOFF
    if cutoff != PRIOR_TAIL_RELAXATION_CUTOFF:
        raise AssertionError("the pinned R7 local-loss cutoff changed")
    if _required_int(tail_certificate, "CANDIDATE_VECTOR_COUNT_AT_CUTOFF_PLUS_ONE") != (
        candidate_count
    ):
        raise AssertionError("R10 cutoff+1 census does not match its R7 candidate count")
    if _required_int(tail_certificate, "VECTORS_AT_EXACT_CUTOFF_PLUS_ONE") != 0:
        raise AssertionError("R10's exact cutoff+1 exclusion is not certified")

    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    ticket_count = r1.TICKET_COUNT - 2
    expanded_limit = cutoff + 2
    vectors = tuple(r6.iter_type_count_vectors(losses, ticket_count, expanded_limit))
    if len(vectors) != candidate_count:
        raise AssertionError(
            "expanding the exact vector census through cutoff+2 changed its cardinality"
        )
    exact_counts: dict[int, int] = {cutoff + 1: 0, cutoff + 2: 0}
    for vector in vectors:
        if len(vector) != len(profiles) or sum(vector) != ticket_count:
            raise AssertionError("the exact loss census emitted an invalid type-count vector")
        loss = sum(count * local_loss for count, local_loss in zip(vector, losses, strict=True))
        if loss > expanded_limit:
            raise AssertionError("the exact loss census emitted a vector above its limit")
        if loss in exact_counts:
            exact_counts[loss] += 1
    if exact_counts[cutoff + 1] != 0 or exact_counts[cutoff + 2] != 0:
        raise AssertionError("a type-count vector exists inside the newly inspected tail shell")

    minimum_omitted_loss = cutoff + 3
    canonical_baseline = _required_int(tail_certificate, "CANONICAL_UNCORRECTED_BASELINE")
    fixed_reduction = _required_int(tail_certificate, "FIXED_BASELINE_REDUCTION_INDEPENDENT_OF_S1")
    primitives = canonical_primitives()
    if canonical_baseline != primitives["K20_S1"] - fixed_reduction:
        raise AssertionError("the canonical uncorrected baseline decomposition changed")
    tightened_tail = canonical_baseline - minimum_omitted_loss
    prior_tail = _required_int(tail_certificate, "CORRECTED_TAIL_BOUND")
    prior_minimum = _required_int(tail_certificate, "MINIMUM_OMITTED_LOCAL_LOSS")
    if prior_minimum != cutoff + 2 or prior_tail != canonical_baseline - prior_minimum:
        raise AssertionError("the prior tail relaxation does not match its certificate")
    if tightened_tail >= prior_tail:
        raise AssertionError("the exact tail spectrum did not tighten the prior tail bound")

    return {
        "LOCAL_LOSS_CUTOFF": cutoff,
        "RESIDUAL_TICKET_COUNT": ticket_count,
        "ANCHOR_INCIDENCE_PROFILE_COUNT": len(profiles),
        "CERTIFIED_CANDIDATE_VECTOR_COUNT_AT_CUTOFF": candidate_count,
        "EXACT_TYPE_VECTOR_COUNT_THROUGH_CUTOFF_PLUS_TWO": len(vectors),
        "VECTORS_AT_EXACT_CUTOFF_PLUS_ONE": exact_counts[cutoff + 1],
        "VECTORS_AT_EXACT_CUTOFF_PLUS_TWO": exact_counts[cutoff + 2],
        "MINIMUM_OMITTED_LOCAL_LOSS": minimum_omitted_loss,
        "FIXED_BASELINE_REDUCTION": fixed_reduction,
        "CANONICAL_UNCORRECTED_BASELINE": canonical_baseline,
        "PRIOR_CORRECTED_TAIL_BOUND": prior_tail,
        "CORRECTED_TAIL_BOUND": tightened_tail,
        "EXACT_CENSUS_WALL_SECONDS": round(time.monotonic() - started, 6),
        "PROOF": (
            "The pinned R7 census contains every 18-ticket type-count vector through "
            "local loss cutoff. Exact R11 enumeration through cutoff+2 has the same "
            "10,816 vectors, so no vector exists at cutoff+1 or cutoff+2. Every omitted "
            "portfolio therefore has integer local loss at least cutoff+3."
        ),
    }


def build_result() -> dict[str, Any]:
    """Build the compact owner-only certificate and final formula check."""

    primitives = canonical_primitives()
    before_terms = top_level_terms()
    before_owners = identify_owner_set(before_terms)
    if before_owners != ("corrected-tail",):
        raise AssertionError(
            f"R10 load-bearing owner is not unique corrected tail: {before_owners}"
        )
    prior_bound = max(term.bound for term in before_terms)
    if prior_bound != PRIOR_R3_BOUND:
        raise AssertionError("the load-bearing term set disagrees with the R3 authority")
    for term in before_terms:
        if term.term_id not in before_owners and term.bound >= prior_bound:
            raise AssertionError(f"non-owner term is not strictly below R3: {term.term_id}")

    tail = exact_tail_spectrum()
    after_terms = tuple(
        BoundTerm(
            term_id=term.term_id,
            bound=(
                _required_int(tail, "CORRECTED_TAIL_BOUND")
                if term.term_id == "corrected-tail"
                else term.bound
            ),
            primitive_dependencies=term.primitive_dependencies,
            structural_certificate_source=(
                "R11_EXACT_30_PROFILE_18_TICKET_TYPE_VECTOR_CENSUS"
                if term.term_id == "corrected-tail"
                else term.structural_certificate_source
            ),
            prior_uncorrected_frontier_bound=term.prior_uncorrected_frontier_bound,
        )
        for term in before_terms
    )
    owners_after = identify_owner_set(after_terms)
    r3_bound = max(term.bound for term in after_terms)
    expected_formula = max(
        _required_int(tail, "CORRECTED_TAIL_BOUND"),
        *(term.bound for term in after_terms if term.term_id != "corrected-tail"),
    )
    if r3_bound != expected_formula or r3_bound != 358_352_827:
        raise AssertionError("the final corrected R3 maximum formula failed")
    if owners_after != ("corrected-tail",):
        raise AssertionError(f"the tightened owner is not unique corrected tail: {owners_after}")
    if any(term.bound >= r3_bound for term in after_terms if term.term_id not in owners_after):
        raise AssertionError("a non-owner term is not strictly below the final R3 bound")

    state_terms = [term for term in after_terms if term.term_id.startswith("state:")]
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_R3_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "CANONICAL_PRIMITIVES": {
            "SINGLE_TICKET_ANY_PRIZE": primitives["SINGLE_TICKET_ANY_PRIZE"],
            "PAIR_INTERSECTION_COST[6]": primitives["PAIR_DIAGONAL_I6"],
            "K20_S1": primitives["K20_S1"],
        },
        "CURRENT_BOUND_OWNER_SET": list(before_owners),
        "OWNER_TERM_COUNT": len(before_owners),
        "TOP_LEVEL_R3_TERMS": [
            {
                "stable_id": term.term_id,
                "bound": term.bound,
                "primitive_dependencies": list(term.primitive_dependencies),
                "structural_certificate_source": term.structural_certificate_source,
                "prior_uncorrected_frontier_bound": term.prior_uncorrected_frontier_bound,
            }
            for term in after_terms
        ],
        "CORRECTED_TAIL_BOUND": tail["CORRECTED_TAIL_BOUND"],
        "TAIL_OWNER_DECOMPOSITION": tail,
        "TOP_STATE_BOUNDS": [
            {"stable_id": term.term_id, "bound": term.bound} for term in state_terms
        ],
        "R3_BOUND": r3_bound,
        "PRIOR_R3_BOUND": prior_bound,
        "R3_STATUS": "CERTIFIED_STRICTLY_BELOW_PRIOR_BOUND",
        "SUCCESS_A": r3_bound <= R4_REFERENCE_BOUND,
        "SUCCESS_B": r3_bound < PRIOR_R3_BOUND,
        "SUCCESS_C": before_owners == ("corrected-tail",),
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": r1.INCUMBENT,
        "REMAINING_GAP": r3_bound - r1.INCUMBENT,
        "SOLVER_STATUS": "NOT_USED_EXACT_TYPE_COUNT_VECTOR_CENSUS",
        "SOLVER_CONFIGURED_WALL_LIMIT": "NOT_APPLICABLE; no solver launched",
        "SOLVER_ACTUAL_WALL_TIME": "NOT_APPLICABLE; no solver launched",
        "SOLVER_CERTIFIED_BOUND": None,
        "EXACT_CENSUS_EXTERNAL_HARD_TIMEOUT_SECONDS": 30,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def write_result() -> dict[str, Any]:
    """Write the requested compact JSON result inside the repository."""

    result = build_result()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(write_result(), indent=2))
