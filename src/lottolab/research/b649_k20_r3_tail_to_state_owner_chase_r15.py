"""Resume R14's attained-loss cursor and chase the exact R3 owner.

R14 left the unclassified tail as the unique owner, 62,776 above the highest
state term.  The canonical tail term is ``K20_S1 - FIXED_CERTIFIED_LOSS -
next_loss``, so it falls to a state bound ``B`` exactly when ``next_loss >=
K20_S1 - FIXED_CERTIFIED_LOSS - B``.  Only the attained levels needed to reach
that loss are classified; R13/R14 levels are fingerprint-checked, never
reclassified.

A state term is an envelope over its R7 region.  R14 refined the members above
its then-competing state and carried the rest at their raw R7 bound, so a
lower competing threshold makes new members load-bearing.  Those members get
R14's solver-independent rational moment certificate; R14-refined members are
carried by fingerprint.  When that certificate cannot strictly lower a
maximizing member, the rational route is exhausted and the chase stops rather
than substituting an unproven bound.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_corrected_tail_min_loss_plateau_r12 as r12
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14
from lottolab.research import b649_k20_r3_tail_threshold_to_top_state_r13 as r13

TASK_ID = "B649_K20_R3_TAIL_TO_STATE_OWNER_CHASE_R15"
BASE_HEAD = "dffe4cc94d4cb7eb9fce968e7371fea1e0fa4bdf"
BASE_TREE = "f3ada2fe9b0410c8d2b4e56aaa13031d0d6bb521"
TASK_BRANCH = "codex/b649-k20-r3-tail-to-state-owner-chase-r15"
START_R3_BOUND = 356_698_986
START_TAIL_BOUND = 356_698_986
START_STATE_MAX_BOUND = 356_636_210
START_STATE_OWNER_ID = "state:s2-12695020-s3-735532"
START_LOSS = 8_349_642
START_CLASSIFIED_MAXIMUM = 356_534_853
START_CROSSOVER_LOSS = 8_412_418
R13_CURSOR_LOSS = 8_249_444
R7_AND_R12_PREFIX_VECTOR_COUNT = 10_816
R14_TAIL_VECTOR_COUNT = 4_125
R4_REFERENCE_BOUND = 350_545_749
INCUMBENT = 313_239_661
DROP_TARGET = 100_000
OWNER_TRANSITION_LIMIT = 8
PROOF_WALL_BUDGET_SECONDS = 3_600.0
INITIAL_CENSUS_WINDOW = 4_096
TAIL_ID = r14.TAIL_ID
STOP_A = "A_R3_AT_OR_BELOW_R4_REFERENCE"
STOP_B = "B_CERTIFIED_R3_DROP_AT_LEAST_100000"
STOP_C = "C_OWNER_TRANSITION_BUDGET_COMPLETED_NEXT_OWNER_IDENTIFIED"
STOP_C_CLASSIFIED = "C_CLASSIFIED_VECTOR_OWNER_IDENTIFIED"
STOP_EXHAUSTED = "STATE_RATIONAL_MOMENT_ROUTE_EXHAUSTED"
STOP_WALL = "PROOF_WALL_BUDGET_EXHAUSTED"
REPO_ROOT = Path(__file__).resolve().parents[3]
R14_RESULT_PATH = r14.RESULT_PATH
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-tail-to-state-owner-chase-r15-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py": (
        "b30f6420eca033bc051ef35457993fc2588ee2e26cc1041363ced5d2c775ce99"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-state-tail-owner-chase-r14-result.json": (
        "5f6c73900469724015fc18d5e713180682ef27ec7f9fa1d98cc7767fea47d115"
    ),
}
CountVector = tuple[int, ...]
StateTerms = tuple[tuple[str, int], ...]
MemberBounds = dict[CountVector, int]
digest = r14.digest
sparse = r14.sparse


class RationalRouteExhausted(Exception):
    """A maximizing owner member already carries the rational moment certificate."""


def dense(pairs: Sequence[Sequence[int]]) -> CountVector:
    counts = [0] * len(r5.anchor_incidence_profiles())
    for index, count in pairs:
        counts[index] = count
    return tuple(counts)


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R14 authority fingerprint mismatch: {observed}")
    return observed


@cache
def authority() -> dict[str, Any]:
    """Pin R14 (and through it the R13 chain) and require the Packet's state."""

    verify_upstream_fingerprints()
    r14.authority()
    stored = cast(dict[str, Any], json.loads(R14_RESULT_PATH.read_text(encoding="utf-8")))
    if (
        stored["TASK_ID"] != r14.TASK_ID
        or stored["R3_BOUND"] != START_R3_BOUND
        or stored["FINAL_OWNER_SET"] != [TAIL_ID]
        or stored["UNCLASSIFIED_TAIL_BOUND"] != START_TAIL_BOUND
        or stored["STATE_MAX_BOUND"] != START_STATE_MAX_BOUND
        or stored["NEXT_UNCLASSIFIED_LOSS"] != START_LOSS
        or stored["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != START_CLASSIFIED_MAXIMUM
        or stored["TAIL_VECTORS_PROCESSED"] != R14_TAIL_VECTOR_COUNT
        or stored["TAIL_LEVEL_CERTIFICATES"][0]["local_loss"] != R13_CURSOR_LOSS
        or stored["TAIL_LEVEL_CERTIFICATES"][-1]["next_unclassified_loss"] != START_LOSS
    ):
        raise AssertionError("R14 authority differs from the R15 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    return r14.canonical_primitives()


def canonical_baseline() -> int:
    """K20_S1 minus the fixed S1-independent R6 reduction (the tail formula)."""

    primitives = canonical_primitives()
    baseline = r12.canonical_uncorrected_baseline()
    if baseline != primitives["K20_S1"] - r13.FIXED_CERTIFIED_LOSS:
        raise AssertionError("the canonical tail baseline changed")
    return baseline


def crossover_loss(target_bound: int) -> int:
    """Return the least next-unclassified loss whose tail term is <= target."""

    primitives = canonical_primitives()
    loss = primitives["K20_S1"] - r13.FIXED_CERTIFIED_LOSS - target_bound
    baseline = canonical_baseline()
    if baseline - loss != target_bound or baseline - (loss - 1) <= target_bound:
        raise AssertionError("the exact crossover arithmetic failed")
    return loss


def initial_state_terms() -> StateTerms:
    rows = cast(list[dict[str, Any]], authority()["CURRENT_STATE_TERMS"])
    terms = tuple((str(row["stable_id"]), int(row["bound"])) for row in rows)
    if len(terms) != 23 or max(bound for _, bound in terms) != START_STATE_MAX_BOUND:
        raise AssertionError("the R14 state terms changed")
    return terms


def r14_refined_members(owner_id: str, region: Sequence[r7.ResidualJointState]) -> MemberBounds:
    """Carry R14's refined members by fingerprint, never by recomputation."""

    records = {
        str(row["owner_id"]): row
        for row in cast(list[dict[str, Any]], authority()["STATE_OWNER_CERTIFICATES"])
    }
    record = records.get(owner_id)
    if record is None:
        return {}
    if record["region_sha256"] != digest(
        tuple((row.witness_counts, r14.raw_bound(row)) for row in region)
    ):
        raise AssertionError("the R14 owner region fingerprint changed")
    threshold = int(record["active_competing_state_threshold"])
    expected = {row.witness_counts: row for row in region if r14.raw_bound(row) >= threshold}
    carried: MemberBounds = {}
    for stored in cast(list[dict[str, Any]], record["region_moment_certificates"]):
        counts = dense(cast(list[list[int]], stored["certificate"]["counts"]))
        state = expected.get(counts)
        if (
            state is None
            or counts in carried
            or stored["raw_bound"] != r14.raw_bound(state)
            or (stored["joint_s2"], stored["joint_s3"]) != (state.joint_s2, state.joint_s3)
            or int(stored["certified_bound"]) > int(stored["raw_bound"])
        ):
            raise AssertionError("an R14 refined member does not match its region state")
        carried[counts] = int(stored["certified_bound"])
    if set(carried) != set(expected):
        raise AssertionError("R14's refined members do not cover its competing threshold")
    return carried


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
    transition_limit: int = OWNER_TRANSITION_LIMIT
    member_bounds: dict[str, MemberBounds] = field(default_factory=lambda: {})
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

    @property
    def transitions(self) -> int:
        return sum(event["from"] != event["to"] for event in self.events)

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
        if self.transitions >= self.transition_limit:
            return STOP_C
        if self.owners == (self.classified_maximum[0],):
            return STOP_C_CLASSIFIED
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

    def improve_state(
        self,
        owner_id: str,
        certificate: dict[str, Any],
        members: Mapping[CountVector, int] | None = None,
    ) -> None:
        self.require_dispatch(owner_id)
        if not owner_id.startswith("state:"):
            raise AssertionError("state certificate applied to a non-state owner")
        before, previous = self.owners, self.bound
        bound = int(certificate["new_bound"])
        if bound >= dict(self.states)[owner_id]:
            raise AssertionError("state certificate is not a strict improvement")
        self.states = tuple(
            (identifier, bound if identifier == owner_id else value)
            for identifier, value in self.states
        )
        if members is not None:
            self.member_bounds[owner_id] = dict(members)
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
                "four_ticket_applied_count": sum(
                    row.four_ticket_status == r13.FOUR_TICKET_APPLIED for row in rows
                ),
                "realizable_count": sum(row.status == r12.WITNESS_REALIZED for row in rows),
                "unrealizable_count": sum(row.status == r12.ELIMINATED for row in rows),
                "unresolved_count": 0,
                "active_state_threshold": self.state_max,
            }
        )
        self._event(f"tail:L{loss}", before, previous)


def represented_vectors(
    members: Sequence[r7.ResidualJointState],
) -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover every R7 census vector that each compressed member stands for."""

    if not members:
        return {}
    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    make_state_api, signature_api = "_make_state", "_state_signature"
    make_state = getattr(r7, make_state_api)
    signature = getattr(r7, signature_api)
    targets = {signature(member): member.witness_counts for member in members}
    if len(targets) != len(members):
        raise AssertionError("two owner members share one R7 compression signature")
    target_losses = {member.local_loss for member in members}
    found: dict[CountVector, list[CountVector]] = {member.witness_counts: [] for member in members}
    for vector in r6.iter_type_count_vectors(
        losses, r12.OUTSIDE_TICKET_COUNT, r7.JOINT_LOCAL_LOSS_CUTOFF
    ):
        if r12.local_loss(vector, losses) not in target_losses:
            continue
        if not r6.aggregate_count_vector_is_feasible(vector):
            continue
        state = make_state(vector, profiles, losses, check_feasibility=False)
        key = targets.get(signature(state))
        if key is not None:
            found[key].append(vector)
    for member in members:
        vectors = found[member.witness_counts]
        if len(vectors) != member.represented_vector_count or min(vectors) != member.witness_counts:
            raise AssertionError("a compressed member's represented vectors were not recovered")
    return {key: tuple(sorted(vectors)) for key, vectors in found.items()}


def certify_state(chase: Chase, owner_id: str) -> tuple[dict[str, Any], MemberBounds]:
    """Refine only the owner envelope's members that are newly load-bearing."""

    chase.require_dispatch(owner_id)
    if not owner_id.startswith("state:"):
        raise AssertionError("state proof requested for a tail owner")
    region = r14.owner_region(owner_id)
    if len({row.witness_counts for row in region}) != len(region):
        raise AssertionError("owner region members are not uniquely keyed")
    prior_bound = dict(chase.states)[owner_id]
    inherited = r14_refined_members(owner_id, region)
    certified = {**inherited, **chase.member_bounds.get(owner_id, {})}
    current = {
        row.witness_counts: certified.get(row.witness_counts, r14.raw_bound(row)) for row in region
    }
    if max(current.values()) != prior_bound:
        raise AssertionError("the state term differs from its envelope maximum")
    maximizing = tuple(row for row in region if current[row.witness_counts] == prior_bound)
    if any(row.witness_counts in certified for row in maximizing):
        raise RationalRouteExhausted(owner_id)
    counts = min(row.witness_counts for row in maximizing)
    support = r12.construct_support_witness(counts)
    if support is None or not r8.validate_support_assignment(counts, support):
        raise AssertionError("owner maximizing support could not be realized")
    witness_s2, witness_s4 = r8.witness_costs(counts, support)

    # Every other term except the descending tail is fixed for this action.
    threshold = max(
        max(bound for identifier, bound in chase.states if identifier != owner_id),
        chase.classified_maximum[1],
    )
    pending = tuple(
        row
        for row in region
        if current[row.witness_counts] >= threshold and row.witness_counts not in certified
    )
    vectors_by_member = represented_vectors(pending)
    refined: list[dict[str, Any]] = []
    updated = dict(certified)
    for row in pending:
        # A compressed member is certified only by its weakest represented vector.
        certificates = [
            r14.moment_certificate(vector) for vector in vectors_by_member[row.witness_counts]
        ]
        correction = max(
            row.applied_residual_union_penalty,
            min(int(certificate["correction_lower_bound"]) for certificate in certificates),
        )
        bound = r14.joint_constant() - row.anchor_pair_s2 + row.anchor_triple_s3 - correction
        if bound > r14.raw_bound(row):
            raise AssertionError("owner moment refinement increased a member's bound")
        updated[row.witness_counts] = bound
        refined.append(
            {
                "joint_s2": row.joint_s2,
                "joint_s3": row.joint_s3,
                "witness_counts": sparse(row.witness_counts),
                "raw_bound": r14.raw_bound(row),
                "certified_bound": bound,
                "represented_vector_count": row.represented_vector_count,
                "vector_certificates": certificates,
            }
        )
    final = {
        row.witness_counts: updated.get(row.witness_counts, current[row.witness_counts])
        for row in region
    }
    new_bound = max(final.values())
    carried = [value for key, value in final.items() if key not in updated]
    record = {
        "owner_id": owner_id,
        "prior_bound": prior_bound,
        "new_bound": new_bound,
        "owner_set_at_dispatch": list(chase.owners),
        "prior_bound_source": (
            "CARRIED_RAW_R7_REGION_MEMBER"
            if all(row.witness_counts not in certified for row in maximizing)
            else "RATIONAL_MOMENT_CERTIFIED_MEMBER"
        ),
        "relaxation_responsible_for_prior_bound": (
            "carried raw R7 envelope: canonical K20 S1 - I(3) - exact anchor S2 + exact "
            "anchor S3 - max(ceil(R6 residual pair floor/9), R5 forest floor); the R6 floor "
            "omits the exact four-event add-back in residual S2"
        ),
        "tightening_route": (
            "d: R14 solver-independent rational residual pair-moment dual with exact "
            "four-event add-back and multiplicity cap 18 (b), applied to every member at "
            "or above the competing threshold"
        ),
        "maximizing_member_count": len(maximizing),
        "maximizing_counts": [sparse(row.witness_counts) for row in maximizing],
        "maximizing_joint_s2_s3": sorted({(row.joint_s2, row.joint_s3) for row in maximizing}),
        "support_witness_counts": sparse(counts),
        "support_witness": support,
        "support_witness_sha256": digest(support),
        "support_witness_validator": "R8 validate_support_assignment and witness_costs",
        "witness_residual_s2": witness_s2,
        "witness_s4": witness_s4,
        "frontier_region_definition": "first dominating R7 frontier point in increasing S2 order",
        "region_compressed_state_count": len(region),
        "region_type_vector_count": sum(row.represented_vector_count for row in region),
        "region_sha256": digest(tuple((row.witness_counts, r14.raw_bound(row)) for row in region)),
        "active_competing_threshold": threshold,
        "inherited_r14_refined_member_count": len(inherited),
        "inherited_r14_refined_maximum": max(inherited.values(), default=None),
        "inherited_r14_refined_sha256": digest(tuple(sorted(inherited.items()))),
        "prior_r15_refined_member_count": len(chase.member_bounds.get(owner_id, {})),
        "new_refined_member_count": len(refined),
        "new_refined_compressed_member_count": sum(
            row.represented_vector_count > 1 for row in pending
        ),
        "new_refined_type_vector_count": sum(row.represented_vector_count for row in pending),
        "new_refined_maximum": max((int(row["certified_bound"]) for row in refined), default=None),
        "carried_raw_member_count": len(carried),
        "carried_raw_maximum": max(carried, default=None),
        "region_moment_certificates": refined,
        "canonical_joint_expression_constant": r14.joint_constant(),
        "s4_solver_attempts": "NOT_DISPATCHED_RATIONAL_CERTIFICATE_STRICT_NOT_LOAD_BEARING",
        "outcome_histogram_used": False,
        "no_other_state_terms_refined": True,
    }
    if len(refined) + len(certified) + len(carried) != len(region):
        raise AssertionError("the owner envelope coverage is incomplete")
    return record, updated


def tail_census(limit: int) -> tuple[tuple[int, tuple[CountVector, ...]], ...]:
    """Enumerate levels through ``limit``; fingerprint, never classify, R13/R14 levels."""

    losses = r6.local_losses(r5.anchor_incidence_profiles())
    prefix = 0
    r14_window: dict[int, list[CountVector]] = {}
    grouped: dict[int, list[CountVector]] = {}
    for counts in r6.iter_type_count_vectors(losses, r12.OUTSIDE_TICKET_COUNT, limit):
        loss = r12.local_loss(counts, losses)
        if loss < R13_CURSOR_LOSS:
            prefix += 1
        elif loss < START_LOSS:
            r14_window.setdefault(loss, []).append(counts)
        else:
            grouped.setdefault(loss, []).append(counts)
    r13_total = int(r14.authority()["TOTAL_CLASSIFIED_VECTOR_COUNT"])
    if prefix != R7_AND_R12_PREFIX_VECTOR_COUNT + r13_total:
        raise AssertionError("the census through the R13 cursor changed")
    stored = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    observed = [
        (loss, len(vectors), digest(tuple(sorted(vectors))))
        for loss, vectors in sorted(r14_window.items())
    ]
    if observed != [
        (int(row["local_loss"]), int(row["vector_count"]), str(row["counts_sha256"]))
        for row in stored
    ]:
        raise AssertionError("the census of R14's classified levels changed")
    levels = tuple((loss, tuple(sorted(grouped[loss]))) for loss in sorted(grouped))
    if not levels or levels[0][0] != START_LOSS:
        raise AssertionError("the first attained level differs from the R14 cursor")
    return levels


def run_chase(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> tuple[Chase, str, float]:
    started = time.monotonic()
    stored = authority()
    chase = Chase(
        states=initial_state_terms(),
        baseline=canonical_baseline(),
        next_loss=START_LOSS,
        classified_maximum=(
            str(stored["MAX_CLASSIFIED_TAIL_VECTOR_ID"]),
            int(stored["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"]),
        ),
    )
    if (
        chase.owners != (TAIL_ID,)
        or chase.tail_bound - chase.state_max != 62_776
        or crossover_loss(chase.state_max) != START_CROSSOVER_LOSS
    ):
        raise AssertionError("the initial coupled owner selection is incorrect")
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, STOP_WALL, time.monotonic() - started
        owner = chase.owners[0]
        if owner.startswith("state:"):
            try:
                certificate, members = certify_state(chase, owner)
            except RationalRouteExhausted:
                return chase, STOP_EXHAUSTED, time.monotonic() - started
            chase.improve_state(owner, certificate, members)
        elif owner == TAIL_ID:
            # Census (not classification) through the first level that can
            # end tail ownership: a state crossover or Success B.
            target = max(
                chase.state_max,
                chase.classified_maximum[1],
                chase.start_bound - chase.drop_target,
            )
            needed = crossover_loss(target)
            window = INITIAL_CENSUS_WINDOW
            while True:
                levels = tail_census(needed + window)
                cursor = next(
                    (index for index, (loss, _) in enumerate(levels) if loss == chase.next_loss),
                    None,
                )
                if cursor is None:
                    raise AssertionError("the tail cursor is not an attained level")
                if levels[-1][0] >= needed and cursor + 1 < len(levels):
                    break
                window *= 2
            for index in range(cursor, len(levels) - 1):
                if (
                    chase.stop_condition() is not None
                    or TAIL_ID not in chase.owners
                    or chase.tail_bound <= chase.state_max
                ):
                    break
                if time.monotonic() - started >= wall_budget:
                    return chase, STOP_WALL, time.monotonic() - started
                loss, vectors = levels[index]
                threshold = chase.state_max
                chase.advance_tail(
                    loss,
                    vectors,
                    levels[index + 1][0],
                    lambda counts, threshold=threshold: r13.classify_vector(
                        counts, chase.baseline, threshold
                    ),
                )
        else:
            raise AssertionError(f"unexpected owner without a stop condition: {owner}")


def build_result() -> dict[str, Any]:
    primitives = canonical_primitives()
    chase, stop, wall = run_chase()
    transitions = [event for event in chase.events if event["from"] != event["to"]]
    initial = dict(initial_state_terms())
    processed = [str(row["owner_id"]) for row in chase.state_records]
    changed = [identifier for identifier, bound in chase.states if bound != initial[identifier]]
    if not set(changed) <= set(processed):
        raise AssertionError("a non-owner state term was changed")
    bound = max(chase.state_max, chase.tail_bound, chase.classified_maximum[1])
    if bound != chase.bound or len(transitions) > OWNER_TRANSITION_LIMIT:
        raise AssertionError("the final maximum or owner-transition budget failed")
    baseline = canonical_baseline()
    owners = chase.owners
    success_c = stop in (STOP_C, STOP_C_CLASSIFIED)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if stop in (STOP_A, STOP_B) or success_c else stop,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "START_R3_BOUND": START_R3_BOUND,
        "START_OWNER_SET": [TAIL_ID],
        "START_OWNER_MARGIN_OVER_STATE": START_TAIL_BOUND - START_STATE_MAX_BOUND,
        "CANONICAL_PRIMITIVES": primitives,
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "CROSSOVER_DERIVATION": {
            "formula": "UNCLASSIFIED_TAIL_BOUND = K20_S1 - FIXED_CERTIFIED_LOSS - next_loss",
            "K20_S1": primitives["K20_S1"],
            "FIXED_CERTIFIED_LOSS": r13.FIXED_CERTIFIED_LOSS,
            "canonical_baseline": baseline,
            "state_max_bound": START_STATE_MAX_BOUND,
            "required_next_unclassified_loss": crossover_loss(START_STATE_MAX_BOUND),
            "tail_at_required_loss": baseline - crossover_loss(START_STATE_MAX_BOUND),
            "tail_one_below_required_loss": baseline - crossover_loss(START_STATE_MAX_BOUND) + 1,
            "success_b_required_next_unclassified_loss": crossover_loss(
                START_R3_BOUND - DROP_TARGET
            ),
        },
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": OWNER_TRANSITION_LIMIT,
        "OWNER_TRANSITIONS": transitions,
        "STATE_OWNERS_PROCESSED": len(chase.state_records),
        "PROCESSED_STATE_OWNER_IDS": processed,
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "TAIL_REALIZABLE_VECTORS": sum(row["realizable_count"] for row in chase.tail_records),
        "TAIL_UNREALIZABLE_VECTORS": sum(row["unrealizable_count"] for row in chase.tail_records),
        "TAIL_FOUR_TICKET_APPLIED_VECTORS": sum(
            row["four_ticket_applied_count"] for row in chase.tail_records
        ),
        "FINAL_BOUND_OWNER": (
            "state"
            if owners[0].startswith("state:")
            else ("tail" if owners[0] == TAIL_ID else "classified-tail-vector")
        ),
        "FINAL_OWNER_IDS": list(owners),
        "STATE_MAX_BOUND": chase.state_max,
        "STATE_MAX_OWNER_IDS": [
            identifier for identifier, value in chase.states if value == chase.state_max
        ],
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
        "SUCCESS_C": success_c,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": PROOF_WALL_BUDGET_SECONDS,
        "SOLVER_STATUS": "NOT_DISPATCHED_RATIONAL_CERTIFICATE_STRICT_S4_NOT_LOAD_BEARING",
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "SOLVER_CERTIFIED_BOUND": None,
        "OUTCOME_HISTOGRAM_USED": False,
        "OUTCOME_CONSERVATION": "NOT_APPLICABLE_NO_OUTCOME_HISTOGRAM_USED",
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "R14_LEVELS_FINGERPRINT_CHECKED": len(
            cast(list[Any], authority()["TAIL_LEVEL_CERTIFICATES"])
        ),
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    options = parser.parse_args()
    result = build_result()
    if not options.no_write:
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "R3_BOUND",
                    "R3_DROP",
                    "OWNER_TRANSITION_COUNT",
                    "STATE_OWNERS_PROCESSED",
                    "TAIL_LEVELS_PROCESSED",
                    "TAIL_VECTORS_PROCESSED",
                    "FINAL_OWNER_IDS",
                    "STATE_MAX_BOUND",
                    "UNCLASSIFIED_TAIL_BOUND",
                    "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
                    "PROOF_WALL_SECONDS",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
