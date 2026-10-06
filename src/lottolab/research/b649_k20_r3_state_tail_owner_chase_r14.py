"""Chase the coupled R13 state/tail maximum, with owner-only certificates.

A frontier term is an envelope, not just its maximizing witness.  Its region
contains the R7 incidence states assigned to the first dominating frontier
point in increasing S2 order.  Refining a witness alone would leave this
region uncovered.  Only the active owner's region receives new moment
inequalities; its nonbinding members keep their exact R7 bounds.

The residual pair moment includes the exact four-event add-back.  A rational
dual converts its lower bound into a union correction for at most 18 residual
winners.  S4 solver attempts are separate: FEASIBLE witnesses are never used
as minimum certificates.  Every strict state improvement or attained tail
level recomputes the entire maximum before any further work is dispatched.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_corrected_tail_min_loss_plateau_r12 as r12
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_tail_threshold_to_top_state_r13 as r13

TASK_ID = "B649_K20_R3_STATE_TAIL_OWNER_CHASE_R14"
MODULE_NAME = "lottolab.research.b649_k20_r3_state_tail_owner_chase_r14"
BASE_HEAD = "bc7341d3f945baabcb33555d02acd5f2bafa0da4"
BASE_TREE = "45982c59c59900a2335121e5f515331fe022871c"
TASK_BRANCH = "codex/b649-k20-r3-state-tail-owner-chase-r14"
START_R3_BOUND = 356_799_210
START_STATE_ID = "state:s2-12695020-s3-735532"
START_TAIL_BOUND = 356_799_184
START_LOSS = 8_249_444
R4_REFERENCE_BOUND = 350_545_749
INCUMBENT = 313_239_661
DROP_TARGET = 100_000
STATE_OWNER_LIMIT = 8
PROOF_WALL_BUDGET_SECONDS = 3_600.0
SOLVER_WORKERS = 2
S4_COMPACT_NATIVE_SECONDS = 60.0
S4_SUPPORT_NATIVE_SECONDS = 90.0
S4_COMPACT_HARD_SECONDS = 80.0
S4_SUPPORT_HARD_SECONDS = 115.0
TAIL_ID = "unclassified-tail"
STOP_A = "A_R3_AT_OR_BELOW_R4_REFERENCE"
STOP_B = "B_CERTIFIED_R3_DROP_AT_LEAST_100000"
STOP_C = "C_EIGHT_STATE_OWNERS_RESOLVED_EXPLICIT_NEXT_OWNER"
STOP_WALL = "PROOF_WALL_BUDGET_EXHAUSTED"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-state-tail-owner-chase-r14-result.json"
)
CountVector = tuple[int, ...]
Support = tuple[tuple[int, ...], ...]
StateTerms = tuple[tuple[str, int], ...]


def digest(payload: object) -> str:
    return sha256(repr(payload).encode("ascii")).hexdigest()


def sparse(counts: CountVector) -> list[list[int]]:
    return [[index, count] for index, count in enumerate(counts) if count]


@cache
def authority() -> dict[str, Any]:
    """Pin R13 and its complete transitive certificate chain, without reruns."""

    r13.verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r13.RESULT_PATH.read_text(encoding="utf-8")))
    if (
        stored["R3_BOUND"] != START_R3_BOUND
        or stored["CURRENT_BOUND_OWNER_SET"] != [START_STATE_ID]
        or stored["UNCLASSIFIED_TAIL_BOUND"] != START_TAIL_BOUND
        or stored["NEXT_UNCLASSIFIED_LOSS"] != START_LOSS
        or stored["MAX_CLASSIFIED_VECTOR_BOUND"] != 356_534_853
    ):
        raise AssertionError("R13 authority differs from the R14 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    primitives = r13.canonical_primitives()
    result = {
        "SINGLE_TICKET_ANY_PRIZE": primitives["SINGLE_TICKET_ANY_PRIZE"],
        "PAIR_INTERSECTION_COST[6]": primitives["PAIR_DIAGONAL_I6"],
        "K20_S1": primitives["K20_S1"],
    }
    if tuple(result.values()) != (18_611_432, 18_611_432, 372_228_640):
        raise AssertionError("canonical primitive preflight failed")
    return result


def initial_state_terms() -> StateTerms:
    rows = cast(list[dict[str, Any]], authority()["TOP_LEVEL_R3_TERMS"])
    terms = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in rows
        if str(row["stable_id"]).startswith("state:")
    )
    if terms != r13.state_terms() or len(terms) != 23:
        raise AssertionError("the frozen 23 state terms changed")
    return terms


def joint_constant() -> int:
    return canonical_primitives()["K20_S1"] - r7.ANCHOR_PAIR_INTERSECTION


def raw_bound(state: r7.ResidualJointState) -> int:
    return joint_constant() - state.joint_s2 + state.joint_s3


@cache
def owner_region(owner_id: str) -> tuple[r7.ResidualJointState, ...]:
    """Recover the active frontier envelope's complete disjoint R7 region."""

    census = r7.joint_residual_census()
    frontier = census.frontier
    target = next(
        (
            point
            for point in frontier
            if f"state:s2-{point.joint_s2}-s3-{point.maximum_joint_s3}" == owner_id
        ),
        None,
    )
    if target is None:
        raise ValueError("unknown state owner")
    rows: list[r7.ResidualJointState] = []
    for state in census.states:
        dominating = next(
            (
                point
                for point in frontier
                if point.joint_s2 <= state.joint_s2 and point.maximum_joint_s3 >= state.joint_s3
            ),
            None,
        )
        if dominating is None:
            raise AssertionError("an R7 state has no frontier dominator")
        if dominating == target:
            rows.append(state)
    if not rows or max(raw_bound(row) for row in rows) != (
        joint_constant() - target.joint_s2 + target.maximum_joint_s3
    ):
        raise AssertionError("the recovered owner region does not attain its frontier term")
    return tuple(rows)


def rational_correction(pair_floor: int, maximum_multiplicity: int = 18) -> int:
    """Certify C >= 2*S2/M by checking every bin with exact rationals."""

    if pair_floor < 0 or maximum_multiplicity < 2:
        raise ValueError("pair floor and multiplicity cap must be valid")
    dual = Fraction(2, maximum_multiplicity)
    for multiplicity in range(maximum_multiplicity + 1):
        correction = max(0, multiplicity - 1)
        if dual * math.comb(multiplicity, 2) > correction:
            raise AssertionError("the rational multiplicity dual is invalid")
    return math.ceil(dual * pair_floor)


def moment_certificate(counts: CountVector) -> dict[str, Any]:
    """An independently replayable rational four-event/pair-moment dual."""

    floor = r8.state_moment_floor(counts)
    profiles = r5.anchor_incidence_profiles()
    pair_rows: list[dict[str, Any]] = []
    minimum_sum = 0
    s4_floor = 0
    for left, left_count in enumerate(counts):
        if not left_count:
            continue
        for right in range(left, len(counts)):
            pair_count = math.comb(left_count, 2) if left == right else left_count * counts[right]
            if not pair_count:
                continue
            table_api = "_pair_event_correction_table"
            table = getattr(r8, table_api)(left, right)
            minimum = min(row[4] for row in table)
            if any(
                Fraction(row[4] - minimum) < floor.minimum_outside_slope * row[3] for row in table
            ):
                raise AssertionError("a four-event row violates the rational outside dual")
            minimum_sum += pair_count * minimum
            s4_floor += pair_count * min(row[5] for row in table)
            pair_rows.append(
                {
                    "types": [left, right],
                    "pair_count": pair_count,
                    "pair_minimum": minimum,
                    "s4_minimum": min(row[5] for row in table),
                    "exact_four_event_table_sha256": digest(table),
                }
            )
    outside_total = sum(
        count * profile.outside for count, profile in zip(counts, profiles, strict=True)
    )
    outside_mass = r6.balanced_pair_mass(outside_total, r6.OUTSIDE_LABEL_CAPACITY)
    exact_floor = minimum_sum + math.ceil(floor.minimum_outside_slope * outside_mass)
    if (
        exact_floor != floor.residual_s2_lower_bound
        or s4_floor != floor.s4_pairwise_minimum_floor
        or outside_mass != floor.outside_pair_mass_floor
    ):
        raise AssertionError("the independent rational pair-moment replay failed")
    return {
        "counts": sparse(counts),
        "residual_s2_lower_bound": exact_floor,
        "pair_minimum_sum": minimum_sum,
        "outside_slope": [
            floor.minimum_outside_slope.numerator,
            floor.minimum_outside_slope.denominator,
        ],
        "outside_incidence_total": outside_total,
        "outside_pair_mass_floor": outside_mass,
        "s4_pairwise_lower_bound": s4_floor,
        "multiplicity_cap": 18,
        "multiplicity_dual": [1, 9],
        "correction_lower_bound": rational_correction(exact_floor),
        "pair_table_rows": pair_rows,
    }


def s4_child(counts: CountVector, kind: str, native_seconds: float) -> dict[str, Any]:
    """Run one bounded model; only OPTIMAL is a solver minimum certificate."""

    cp_model: Any = importlib.import_module("ortools.sat.python.cp_model")
    runtime = r8.solver_runtime_preflight()
    started = time.monotonic()
    if kind == "compact":
        builder = "_build_compact_frequency_s4_model"
        model, objective = getattr(r8, builder)(counts)
        labels = None
    elif kind == "support":
        builder = "_build_state_optimization_model"
        optimization = getattr(r8, builder)(counts)
        model = optimization.incidence.model
        objective = sum(optimization.s4_costs)
        model.Minimize(objective)
        labels = optimization.incidence.ticket_labels
    else:
        raise ValueError("unknown S4 model")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = native_seconds
    solver.parameters.num_search_workers = SOLVER_WORKERS
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    incumbent = int(solver.Value(objective)) if solution else None
    support: Support | None = None
    if solution and labels is not None:
        support = tuple(
            tuple(label for label, value in enumerate(ticket) if solver.Value(value))
            for ticket in labels
        )
        if not r8.validate_support_assignment(counts, support):
            raise AssertionError("solver support failed independent validation")
        if r8.witness_costs(counts, support)[1] != incumbent:
            raise AssertionError("solver S4 objective failed independent four-event replay")
    return {
        "kind": kind,
        "status": solver.StatusName(status),
        "incumbent_s4": incumbent,
        "observed_best_objective_bound_not_a_proof": float(solver.BestObjectiveBound()),
        "certified_minimum": incumbent if status == cp_model.OPTIMAL else None,
        "minimum_scope": "FREQUENCY_RELAXATION" if kind == "compact" else "FULL_SUPPORT",
        "support": support,
        "native_wall_limit_seconds": native_seconds,
        "solver_wall_seconds": solver.WallTime(),
        "child_wall_seconds": time.monotonic() - started,
        "workers": SOLVER_WORKERS,
        "runtime": runtime,
    }


def run_s4_attempt(counts: CountVector, kind: str) -> dict[str, Any]:
    native = S4_COMPACT_NATIVE_SECONDS if kind == "compact" else S4_SUPPORT_NATIVE_SECONDS
    hard = S4_COMPACT_HARD_SECONDS if kind == "compact" else S4_SUPPORT_HARD_SECONDS
    started = time.monotonic()
    env = dict(os.environ)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(REPO_ROOT / "src"),
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    command = [
        sys.executable,
        "-m",
        MODULE_NAME,
        "--s4-child",
        kind,
        "--counts",
        json.dumps(counts),
        "--native-seconds",
        str(native),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, env=env, check=False, timeout=hard
        )
    except subprocess.TimeoutExpired:
        return {
            "kind": kind,
            "status": "EXTERNAL_HARD_TIMEOUT",
            "certified_minimum": None,
            "native_wall_limit_seconds": native,
            "external_hard_timeout_seconds": hard,
            "external_wall_seconds": time.monotonic() - started,
            "termination": "subprocess.run terminated task-owned child on timeout",
        }
    if completed.returncode:
        raise RuntimeError("S4 child failed: " + completed.stderr[-2_000:])
    result = cast(dict[str, Any], json.loads(completed.stdout))
    result["external_hard_timeout_seconds"] = hard
    result["external_wall_seconds"] = time.monotonic() - started
    return result


@dataclass
class Chase:
    """The live maximum is the sole dispatch authority for state and tail work."""

    states: StateTerms
    baseline: int
    next_loss: int
    classified_maximum: tuple[str, int]
    start_bound: int = START_R3_BOUND
    r4_reference: int = R4_REFERENCE_BOUND
    drop_target: int = DROP_TARGET
    state_limit: int = STATE_OWNER_LIMIT
    state_records: list[dict[str, Any]] = field(default_factory=lambda: [])
    tail_records: list[dict[str, Any]] = field(default_factory=lambda: [])
    events: list[dict[str, Any]] = field(default_factory=lambda: [])

    @property
    def terms(self) -> StateTerms:
        return (*self.states, (TAIL_ID, self.tail_bound), self.classified_maximum)

    @property
    def tail_bound(self) -> int:
        return self.baseline - self.next_loss

    @property
    def bound(self) -> int:
        return max(bound for _, bound in self.terms)

    @property
    def owners(self) -> tuple[str, ...]:
        return r13.identify_owner_set(self.terms)

    @property
    def state_max(self) -> int:
        return max(bound for _, bound in self.states)

    def require_owner(self, owner_id: str) -> None:
        if owner_id not in self.owners:
            raise AssertionError(f"non-owner work forbidden: {owner_id}; owners={self.owners}")

    def require_dispatch(self, owner_id: str) -> None:
        self.require_owner(owner_id)
        stop = self.stop_condition()
        if stop is not None:
            raise AssertionError(f"work after stop condition is forbidden: {stop}")

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        # Finish any required tail transition before the eight-owner handoff.
        if len(self.state_records) >= self.state_limit and TAIL_ID not in self.owners:
            return STOP_C
        return None

    def _event(self, action: str, before: tuple[str, ...], previous_bound: int) -> None:
        if self.bound > previous_bound:
            raise AssertionError("a completed owner action must not increase R3")
        self.events.append(
            {
                "ordinal": len(self.events) + 1,
                "action": action,
                "from": list(before),
                "to": list(self.owners),
                "r3_bound": self.bound,
                "state_max_bound": self.state_max,
                "unclassified_tail_bound": self.tail_bound,
                "max_classified_tail_vector_bound": self.classified_maximum[1],
                "next_unclassified_loss": self.next_loss,
            }
        )

    def improve_state(self, owner_id: str, certificate: dict[str, Any]) -> None:
        self.require_dispatch(owner_id)
        if not owner_id.startswith("state:") or len(self.state_records) >= self.state_limit:
            raise AssertionError("state dispatch exceeds its owner or batch boundary")
        before, previous = self.owners, self.bound
        bound = int(certificate["new_bound"])
        prior = dict(self.states)[owner_id]
        if bound >= prior:
            raise AssertionError("state certificate is not a strict improvement")
        self.states = tuple(
            (identifier, bound if identifier == owner_id else value)
            for identifier, value in self.states
        )
        self.state_records.append(certificate)
        self._event(f"state:{owner_id}", before, previous)

    def advance_tail(
        self,
        loss: int,
        vectors: Sequence[CountVector],
        next_loss: int,
        classify: Callable[[CountVector], r13.ClassifiedVector],
    ) -> None:
        self.require_dispatch(TAIL_ID)
        if self.tail_bound <= self.state_max:
            raise AssertionError("tail descent below the active state threshold is forbidden")
        if loss != self.next_loss or next_loss <= loss or not vectors:
            raise AssertionError("tail dispatch must use the next complete attained level")
        before, previous = self.owners, self.bound
        rows = tuple(classify(counts) for counts in vectors)
        for row in rows:
            if row.local_loss != loss or row.status not in (r12.WITNESS_REALIZED, r12.ELIMINATED):
                raise AssertionError("tail level contains an unresolved or misplaced vector")
            if row.status == r12.WITNESS_REALIZED and (
                row.witness is None or not r8.validate_support_assignment(row.counts, row.witness)
            ):
                raise AssertionError("tail support witness failed independent validation")
            if row.vector_bound is not None:
                if row.vector_bound > self.baseline - loss:
                    raise AssertionError("tail correction cannot be negative")
                if row.vector_bound > self.classified_maximum[1]:
                    self.classified_maximum = row.vector_id, row.vector_bound
        self.next_loss = next_loss
        self.tail_records.append(
            {
                "local_loss": loss,
                "next_unclassified_loss": next_loss,
                "vector_count": len(rows),
                "counts_sha256": digest(tuple(row.counts for row in rows)),
                "support_witness_sha256": digest(tuple(row.witness for row in rows)),
                "classified_rows_sha256": digest(rows),
                "maximum_new_vector_bound": max(
                    (row.vector_bound for row in rows if row.vector_bound is not None), default=None
                ),
                "realizable_count": sum(row.status == r12.WITNESS_REALIZED for row in rows),
                "unrealizable_count": sum(row.status == r12.ELIMINATED for row in rows),
                "unresolved_count": 0,
                "active_state_threshold": self.state_max,
            }
        )
        self._event(f"tail:L{loss}", before, previous)


def certify_state(chase: Chase, owner_id: str, *, use_solvers: bool = True) -> dict[str, Any]:
    """Close one active envelope; leave every other state term untouched."""

    chase.require_dispatch(owner_id)
    if not owner_id.startswith("state:"):
        raise AssertionError("state proof requested for a tail owner")
    region = owner_region(owner_id)
    prior_bound = dict(chase.states)[owner_id]
    maximum_s3 = max(row.joint_s3 for row in region)
    maximizing = tuple(row for row in region if raw_bound(row) == prior_bound)
    if not maximizing:
        raise AssertionError("the current owner has no exact frontier maximizing member")
    counts = min(row.witness_counts for row in maximizing)
    support = r12.construct_support_witness(counts)
    if support is None:
        raise AssertionError("owner maximizing support could not be realized")
    witness_pair, witness_s4 = r8.witness_costs(counts, support)
    floor = moment_certificate(counts)
    attempts = (
        [run_s4_attempt(counts, "compact"), run_s4_attempt(counts, "support")]
        if use_solvers
        else []
    )
    certified_s4 = int(floor["s4_pairwise_lower_bound"])
    best_support = support
    exact_s4 = False
    for attempt in attempts:
        if attempt.get("certified_minimum") is not None:
            if attempt.get("status") != "OPTIMAL":
                raise AssertionError("a non-OPTIMAL S4 attempt cannot certify a minimum")
            certified_s4 = max(certified_s4, int(attempt["certified_minimum"]))
        if attempt.get("support") is not None:
            candidate = tuple(tuple(int(label) for label in row) for row in attempt["support"])
            candidate_s4 = r8.witness_costs(counts, candidate)[1]
            if candidate_s4 < witness_s4:
                best_support, witness_s4 = candidate, candidate_s4
    exact_s4 = witness_s4 == certified_s4

    # The region is the active term's domain.  Members already below every
    # competing state require no new classification or moment evaluation.
    threshold = max(bound for identifier, bound in chase.states if identifier != owner_id)
    refined: list[dict[str, Any]] = []
    remainder: list[int] = []
    for row in region:
        prior = raw_bound(row)
        if prior < threshold:
            remainder.append(prior)
            continue
        if row.represented_vector_count != 1:
            raise AssertionError("a compressed owner member needs vector-wise moment certificates")
        certificate = moment_certificate(row.witness_counts)
        correction = max(
            row.applied_residual_union_penalty, int(certificate["correction_lower_bound"])
        )
        bound = joint_constant() - row.anchor_pair_s2 + row.anchor_triple_s3 - correction
        if bound > prior:
            raise AssertionError("owner moment refinement increased a member's bound")
        refined.append(
            {
                "joint_s2": row.joint_s2,
                "joint_s3": row.joint_s3,
                "raw_bound": prior,
                "certified_bound": bound,
                "certificate": certificate,
                "represented_vector_count": row.represented_vector_count,
            }
        )
    new_bound = max(*(int(row["certified_bound"]) for row in refined), max(remainder, default=0))
    if len(refined) + len(remainder) != len(region):
        raise AssertionError("the owner envelope coverage is incomplete")
    representative = next(row for row in maximizing if row.witness_counts == counts)
    return {
        "owner_id": owner_id,
        "prior_bound": prior_bound,
        "new_bound": new_bound,
        "joint_s2": representative.joint_s2,
        "maximum_joint_s3": maximum_s3,
        "exact_anchor_s2": representative.anchor_pair_s2,
        "exact_anchor_s3": representative.anchor_triple_s3,
        "legacy_residual_pair_floor": representative.residual_pair_intersection_mass_floor,
        "legacy_union_correction": representative.applied_residual_union_penalty,
        "relaxation_responsible_for_prior_bound": (
            "canonical K20 S1 - I(3) - exact anchor S2 + exact anchor S3 "
            "- max(ceil(R6 residual pair floor/9), R5 forest floor); "
            "R6 floor omits the exact four-event add-back in residual S2"
        ),
        "maximizing_vector_count": sum(row.represented_vector_count for row in maximizing),
        "maximizing_counts": [sparse(row.witness_counts) for row in maximizing],
        "support_witness": best_support,
        "support_witness_sha256": digest(best_support),
        "support_witness_validator": "R8 validate_support_assignment and witness_costs",
        "witness_residual_s2": r8.witness_costs(counts, best_support)[0],
        "initial_witness_residual_s2": witness_pair,
        "s4": {
            "scope": "sum of intersections A,B,C_i,C_j at the exact S3 maximizing vector",
            "certified_lower_bound": certified_s4,
            "feasible_upper_bound": witness_s4,
            "minimum_proven": exact_s4,
            "proof_source": "OPTIMAL_OR_INDEPENDENT_LOWER_BOUND_ATTAINED"
            if exact_s4
            else ("INDEPENDENT_PAIR_TABLE_FLOOR; FEASIBLE_SOLVER_BOUNDS_NOT_USED"),
            "attempts": attempts,
        },
        "existing_higher_order_certificate": "NONE_FOR_THIS_R13_OWNER",
        "higher_order_route": [
            "a: bounded exact S4 attempts at S3 maximizers",
            "b: structural winning-ticket multiplicity cap 18",
            "d: solver-independent rational residual moment dual",
        ],
        "frontier_region_definition": "first dominating R7 frontier point in increasing S2 order",
        "region_compressed_state_count": len(region),
        "region_type_vector_count": sum(row.represented_vector_count for row in region),
        "region_sha256": digest(tuple((row.witness_counts, raw_bound(row)) for row in region)),
        "active_competing_state_threshold": threshold,
        "refined_region_member_count": len(refined),
        "carried_region_member_count": len(remainder),
        "carried_region_maximum": max(remainder, default=0),
        "refined_region_maximum": max(int(row["certified_bound"]) for row in refined),
        "region_moment_certificates": refined,
        "canonical_joint_expression_constant": joint_constant(),
        "no_other_state_terms_refined": True,
        "outcome_histogram_used": False,
    }


def tail_census(limit: int) -> tuple[tuple[int, tuple[CountVector, ...]], ...]:
    """Enumerate loss levels, without classifying pre-cursor or future vectors."""

    losses = r6.local_losses(r5.anchor_incidence_profiles())
    grouped: dict[int, list[CountVector]] = {}
    prior_count = 0
    for counts in r6.iter_type_count_vectors(losses, 18, limit):
        loss = r12.local_loss(counts, losses)
        if loss < START_LOSS:
            prior_count += 1
        else:
            grouped.setdefault(loss, []).append(counts)
    expected = 10_816 + int(authority()["TOTAL_CLASSIFIED_VECTOR_COUNT"])
    if prior_count != expected:
        raise AssertionError("the census through the R13 cursor changed")
    levels = tuple((loss, tuple(sorted(grouped[loss]))) for loss in sorted(grouped))
    if not levels or levels[0][0] != START_LOSS:
        raise AssertionError("the first attained level differs from the R13 cursor")
    return levels


def run_chase(*, use_solvers: bool = True) -> tuple[Chase, str, float]:
    started = time.monotonic()
    stored = authority()
    chase = Chase(
        states=initial_state_terms(),
        baseline=r12.canonical_uncorrected_baseline(),
        next_loss=START_LOSS,
        classified_maximum=(
            str(stored["MAX_CLASSIFIED_VECTOR_ID"]),
            int(stored["MAX_CLASSIFIED_VECTOR_BOUND"]),
        ),
    )
    if chase.owners != (START_STATE_ID,) or chase.state_max - chase.tail_bound != 26:
        raise AssertionError("the initial coupled owner selection is incorrect")
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= PROOF_WALL_BUDGET_SECONDS:
            return chase, STOP_WALL, time.monotonic() - started
        owner = chase.owners[0]
        if owner.startswith("state:"):
            certificate = certify_state(chase, owner, use_solvers=use_solvers)
            chase.improve_state(owner, certificate)
        elif owner == TAIL_ID:
            # Enough census for either the current state crossover or Success B,
            # plus a following attained level. Census is not classification.
            threshold = max(chase.state_max, chase.start_bound - chase.drop_target)
            window = 4_096
            while True:
                levels = tail_census(chase.baseline - threshold + window)
                cursor = next(
                    index for index, (loss, _) in enumerate(levels) if loss == chase.next_loss
                )
                if cursor + 1 < len(levels):
                    break
                window *= 2
            for index in range(cursor, len(levels) - 1):
                if chase.stop_condition() is not None or TAIL_ID not in chase.owners:
                    break
                if time.monotonic() - started >= PROOF_WALL_BUDGET_SECONDS:
                    return chase, STOP_WALL, time.monotonic() - started
                loss, vectors = levels[index]
                next_loss = levels[index + 1][0]
                threshold = chase.state_max
                chase.advance_tail(
                    loss,
                    vectors,
                    next_loss,
                    lambda counts, threshold=threshold: r13.classify_vector(
                        counts, chase.baseline, threshold
                    ),
                )
        else:
            # Classified vector owners are explicit proof barriers, not a
            # license to start unrelated state work.
            raise AssertionError(f"classified tail vector requires its own certificate: {owner}")


def build_result(*, use_solvers: bool = True) -> dict[str, Any]:
    primitives = canonical_primitives()
    runtime = r8.solver_runtime_preflight() if use_solvers else None
    chase, stop, wall = run_chase(use_solvers=use_solvers)
    transitions = [event for event in chase.events if event["from"] != event["to"]]
    attempts = [attempt for state in chase.state_records for attempt in state["s4"]["attempts"]]
    solver_wall = sum(float(attempt["external_wall_seconds"]) for attempt in attempts)
    initial = dict(initial_state_terms())
    processed = {str(row["owner_id"]) for row in chase.state_records}
    if any(
        bound != initial[identifier]
        for identifier, bound in chase.states
        if identifier not in processed
    ):
        raise AssertionError("a non-owner state term was changed")
    bound = max(chase.state_max, chase.tail_bound, chase.classified_maximum[1])
    if bound != chase.bound or len(chase.state_records) > STATE_OWNER_LIMIT:
        raise AssertionError("the final maximum or state-owner budget failed")
    fingerprints = {
        str(path.relative_to(REPO_ROOT)): sha256(path.read_bytes()).hexdigest()
        for path in (Path(r13.__file__), r13.RESULT_PATH)
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if stop in (STOP_A, STOP_B, STOP_C) else stop,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "START_R3_BOUND": START_R3_BOUND,
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITIONS": transitions,
        "STATE_OWNERS_PROCESSED": len(chase.state_records),
        "PROCESSED_STATE_OWNER_IDS": [row["owner_id"] for row in chase.state_records],
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "FINAL_BOUND_OWNER": "state" if chase.owners[0].startswith("state:") else "tail",
        "FINAL_OWNER_ID": chase.owners[0],
        "FINAL_OWNER_SET": list(chase.owners),
        "STATE_MAX_BOUND": chase.state_max,
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "CURRENT_STATE_TERMS": [
            {"stable_id": identifier, "bound": value} for identifier, value in chase.states
        ],
        "STATE_OWNER_CERTIFICATES": chase.state_records,
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "R3_BOUND": bound,
        "R3_STATUS": "CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R3_DROP": START_R3_BOUND - bound,
        "R3_FORMULA": (
            "max(CURRENT_STATE_TERMS, UNCLASSIFIED_TAIL_BOUND, CLASSIFIED_TAIL_VECTOR_BOUNDS)"
        ),
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": bound - INCUMBENT,
        "STOP_CONDITION": stop,
        "SUCCESS_A": bound <= R4_REFERENCE_BOUND,
        "SUCCESS_B": START_R3_BOUND - bound >= DROP_TARGET,
        "SUCCESS_C": stop == STOP_C and len(chase.owners) == 1,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": PROOF_WALL_BUDGET_SECONDS,
        "STATE_OWNER_LIMIT": STATE_OWNER_LIMIT,
        "SOLVER_RUNTIME_PREFLIGHT": runtime,
        "SOLVER_STATUS": "S4_ATTEMPTS_SEPARATE_FROM_SOLVER_INDEPENDENT_BOUND"
        if use_solvers
        else "NOT_USED",
        "SOLVER_CONFIGURED_WALL_LIMIT": {
            "compact_native": S4_COMPACT_NATIVE_SECONDS,
            "compact_external": S4_COMPACT_HARD_SECONDS,
            "support_native": S4_SUPPORT_NATIVE_SECONDS,
            "support_external": S4_SUPPORT_HARD_SECONDS,
        },
        "SOLVER_ACTUAL_WALL_TIME": solver_wall,
        "SOLVER_CERTIFIED_BOUND": None,
        "SOLVER_BOUND_EXPLANATION": (
            "R3 proof uses exact rational inequalities; only OPTIMAL S4 minima or "
            "independently attained lower bounds are certificates. FEASIBLE objective "
            "bounds are observation only."
        ),
        "SOLVER_WORKERS": SOLVER_WORKERS,
        "OUTCOME_HISTOGRAM_USED": False,
        "OUTCOME_CONSERVATION": "NOT_APPLICABLE_NO_OUTCOME_HISTOGRAM_USED",
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s4-child", choices=("compact", "support"))
    parser.add_argument("--counts")
    parser.add_argument("--native-seconds", type=float, default=S4_COMPACT_NATIVE_SECONDS)
    options = parser.parse_args()
    if options.s4_child:
        counts = tuple(cast(list[int], json.loads(options.counts)))
        print(json.dumps(s4_child(counts, options.s4_child, options.native_seconds)))
    else:
        result = build_result()
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in (
                        "TASK_STATUS",
                        "R3_BOUND",
                        "R3_DROP",
                        "STATE_OWNERS_PROCESSED",
                        "TAIL_LEVELS_PROCESSED",
                        "FINAL_OWNER_ID",
                    )
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
