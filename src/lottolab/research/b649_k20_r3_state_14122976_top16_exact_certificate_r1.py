"""Zero-solver Top-16 certificate for the R7 S3 window (R1).

Two exhaustive bounded recurrences project only the R7 local-loss domain in
951748 < S3 <= 1005536. The ascending recurrence prunes by a suffix S3 bound;
the independent descending recurrence subtracts S3/loss budgets. Neither runs
the R7 census. R7's complete compression signature and ordering are retained.

The R7 cutoff is part of the State domain, not an infeasibility assertion:
vectors above it belong to the separately carried Tail authority. Aggregate
feasibility is only R6's necessary relaxation. Unwitnessed members retain their
valid raw upper bound; absence of a support witness never deletes a member.

Only members above the competing 355637030 State threshold receive R14 credit.
For a compressed member the smallest vector correction is combined by max with
the R7 forest/R6 correction already in its raw bound. Other State owners and the
base family authority are carried unchanged; this is a State-local certificate.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_tail_crossover_state_dynamic_chase_r24 as r24

r14, r12, r8, r6, r5 = r24.r14, r24.r12, r24.r8, r24.r6, r24.r5
CountVector = tuple[int, ...]
sparse, dense, digest = r24.sparse, r24.dense, r24.digest
TASK_ID = "B649_K20_R3_STATE_14122976_TOP16_EXACT_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-14122976-top16-exact-certificate-r1"
BASE_HEAD = "9f3658eaae8db9bad68cee6eeb078418ddd370c0"
BASE_TREE = "8ad4e8f368846ebd8c111ca8a0575b329ace45f0"
R24_SOURCE = "27614636ac4c20392619b3d9364d22bf2af9cff4"
R24_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
STATE_ID = "state:s2-14122976-s3-1005536"
S2_MIN, S3_LOWER, S3_UPPER = 14_122_976, 951_748, 1_005_536
START_STATE_BOUND = 355_641_258
TOP_THRESHOLD = 355_637_030
EXPECTED_STATE_BOUND = 355_510_148
EXPECTED_TOP_MAX = 353_458_878
REGION_SHA256 = "785409687cbaca559e536cf63ff87fb0e5f972796025ef03743e13ba5a88555e"
COMBINATION = "MAX(R7_APPLIED_CORRECTION, MIN_REPRESENTED_VECTOR_R14_CORRECTION)"
REPO_ROOT = Path(__file__).resolve().parents[3]
R7_RELATIVE = r24.RESULTS + "b649-k20-r3-joint-residual-envelope-r7-result.json"
R24_RELATIVE = r24.RESULTS + "b649-k20-r3-tail-crossover-state-dynamic-chase-r24-result.json"
BASE_RELATIVE = r24.RESULTS + "b649-k20-r3-tail-state-combined-authority-r1-result.json"
RESULT_PATH = REPO_ROOT / (
    r24.RESULTS + "b649-k20-r3-state-14122976-top16-exact-certificate-r1-result.json"
)
# Literal hashes of immutable source bytes, populated before any task implementation.
UPSTREAM_SHA256: dict[str, str] = {
    "src/lottolab/research/b649_k20_outside_min_s2_global_penalty_bound_r1.py": (
        "7706e57e77df6e786e77c4824f3c72663fdae73b20aa5f6797192689f2b6ea62"
    ),
    "src/lottolab/research/b649_k20_r3_anchor_incidence_bound_r5.py": (
        "569d525f1e9905d043fe0f6132c936d5b260ba3d4b3a376da6c961db8aa5c435"
    ),
    "src/lottolab/research/b649_k20_r3_bound_owner_reduction_r11.py": (
        "9a344dc2d6c03fb45e9cb105661dbda58c55eea9db6c93eed12ff998e5f403fc"
    ),
    "src/lottolab/research/b649_k20_r3_canonical_primitive_authority_repair_r10.py": (
        "993da1bf527635482bd3d9cb2ddc9c290ebf9e7abba7d2f3fe483f3a56886acd"
    ),
    "src/lottolab/research/b649_k20_r3_classified_tail_band_to_state_r21.py": (
        "9809146ae3bf07d9739007dee9ce886b262bce223f85f74066eb1d7de46a28cb"
    ),
    "src/lottolab/research/b649_k20_r3_corrected_tail_min_loss_plateau_r12.py": (
        "4501b7a496d32a87bdbfa2d4e0951bca330a60feb8b799350cc0a76607008c92"
    ),
    "src/lottolab/research/b649_k20_r3_cursor_resolved_three_class_owner_chase_r19.py": (
        "dfe99452a5dfc32a1aca697729975592dd02afd14726d04077c15f2297d65e8a"
    ),
    "src/lottolab/research/b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py": (
        "a83f6f2a7091aedf034e0905d80993df5001382fedc297fdd503202665e6622c"
    ),
    "src/lottolab/research/b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
    "src/lottolab/research/b649_k20_r3_joint_residual_envelope_r7.py": (
        "f376899a25bc287e45b80c3f5d9116db97f4c09de31ec81d0ccd2badf4222c50"
    ),
    "src/lottolab/research/b649_k20_r3_state_tail_coupled_owner_chase_r22.py": (
        "945c1b06ca35262c200c33e83de1ba8196cb13f75151ec25f85b1ae15d37f1d5"
    ),
    "src/lottolab/research/b649_k20_r3_state_tail_owner_chase_r14.py": (
        "b30f6420eca033bc051ef35457993fc2588ee2e26cc1041363ced5d2c775ce99"
    ),
    "src/lottolab/research/b649_k20_r3_tail_crossover_and_state_refinement_r20.py": (
        "f3791b46291a549bc49717b05f4a2c39a75eea5204feb3b9a242455d8f73848b"
    ),
    "src/lottolab/research/b649_k20_r3_tail_crossover_state_dynamic_chase_r24.py": (
        "2a5e57a7319bd215f8cbc7f4db26453308a74c3f540c25787c44604aa39c8fd7"
    ),
    "src/lottolab/research/b649_k20_r3_tail_state_owner_chase_r16.py": (
        "7296c471b63e728e8d873878d96bf3ab84a78a951a288d4dd87aeea1cd882b9f"
    ),
    "src/lottolab/research/b649_k20_r3_tail_state_owner_chase_r17.py": (
        "0edad246de25771745a215b0d922fc27e8839c40472a2f9859dc9a242a000a3b"
    ),
    "src/lottolab/research/b649_k20_r3_tail_threshold_to_top_state_r13.py": (
        "d5ad668a4338a5146d45ea82be5f0def8210a8005b8ed2ec70e8303da19cc918"
    ),
    "src/lottolab/research/b649_k20_r3_tail_to_state_dynamic_chase_r23.py": (
        "9ba9dc55b14a14aabad2c21c9a03da4058e12c3dede959c3f050c88424e73c5e"
    ),
    "src/lottolab/research/b649_k20_r3_tail_to_state_owner_chase_r15.py": (
        "e1daab84f1ca47fa6ba1f2a75650f1e0fa9931984b5f0c662228f99391fced5f"
    ),
    "src/lottolab/research/b649_k20_r3_three_class_owner_chase_r18.py": (
        "e29cad7477b4572c838c19ba5af7228ad5f7216b9042ab55d170f000b113dcc9"
    ),
    R24_RELATIVE: "32182a3c3c803d95b3a7aee448f8ade3fadb291771affc9dca8beaab8147fc71",
    BASE_RELATIVE: "f7af7f348825a7bab7d21b294a2fdd90c1078cc948116cf06b150c9722be6326",
    R7_RELATIVE: "463f0e1d577e5e175822d7fc52b1237fd7eb750fbd8ac654280993c160051f02",
}


def stored(relative: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((REPO_ROOT / relative).read_text(encoding="utf-8")))


def normalized(payload: object) -> Any:
    return json.loads(json.dumps(payload))


def verify_sources() -> dict[str, str]:
    observed = {
        name: sha256((REPO_ROOT / name).read_bytes()).hexdigest() for name in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    for head, tree in ((BASE_HEAD, BASE_TREE), (R24_SOURCE, R24_TREE)):
        actual = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", f"{head}^{{tree}}"], text=True
        ).strip()
        if actual != tree:
            raise AssertionError("immutable commit/tree provenance mismatch")
    r24.verify_upstream_fingerprints()
    return observed


def validate_domain(
    weights: Sequence[int], losses: Sequence[int], tickets: int, lower: int, upper: int, cutoff: int
) -> None:
    if (
        len(weights) != len(losses)
        or not weights
        or weights[0] != 0
        or losses[0] != 0
        or any(x <= 0 for x in (*weights[1:], *losses[1:]))
        or min(tickets, lower, cutoff) < 0
        or upper < lower
    ):
        raise ValueError("invalid bounded S3/loss domain")


def ascending_vectors(
    weights: Sequence[int], losses: Sequence[int], tickets: int, lower: int, upper: int, cutoff: int
) -> Iterator[CountVector]:
    """All count vectors in the window: every type count has every legal integer split.

    Zero type fills the remaining tickets. Suffix maximum bounds all future S3;
    positive S3/loss increments justify both budget upper bounds. No feasible
    completion is pruned. This is a bounded S3 projection, not a full loss census.
    """

    validate_domain(weights, losses, tickets, lower, upper, cutoff)
    counts = [0] * len(weights)
    suffix_max = [max(weights[i:], default=0) for i in range(len(weights) + 1)]

    def visit(index: int, remaining: int, s3: int, loss: int) -> Iterator[CountVector]:
        if s3 + remaining * suffix_max[index] < lower:
            return
        if index == len(weights):
            counts[0] = remaining
            yield tuple(counts)
            counts[0] = 0
            return
        maximum = min(remaining, (upper - s3) // weights[index], (cutoff - loss) // losses[index])
        for amount in range(maximum + 1):
            counts[index] = amount
            yield from visit(
                index + 1,
                remaining - amount,
                s3 + amount * weights[index],
                loss + amount * losses[index],
            )
        counts[index] = 0

    yield from visit(1, tickets, 0, 0)


def descending_vectors(
    weights: Sequence[int], losses: Sequence[int], tickets: int, lower: int, upper: int, cutoff: int
) -> Iterator[CountVector]:
    """Independent budget-subtraction recurrence, largest S3 type first.

    This uses neither the ascending traversal nor its suffix pruning. Each legal
    count split subtracts both budgets; the leaf checks the lower S3 endpoint.
    The positive increments make overspent-budget rejection exact.
    """

    validate_domain(weights, losses, tickets, lower, upper, cutoff)
    order = sorted(range(1, len(weights)), key=lambda i: (weights[i], losses[i], i), reverse=True)

    def expand(
        position: int, left: int, s3_budget: int, loss_budget: int, allocation: tuple[int, ...]
    ) -> Iterator[CountVector]:
        if position == len(order):
            if upper - s3_budget >= lower:
                counts = [0] * len(weights)
                counts[0] = left
                for index, amount in zip(order, allocation, strict=True):
                    counts[index] = amount
                yield tuple(counts)
            return
        index = order[position]
        limit = min(left, s3_budget // weights[index], loss_budget // losses[index])
        for amount in range(limit, -1, -1):
            yield from expand(
                position + 1,
                left - amount,
                s3_budget - amount * weights[index],
                loss_budget - amount * losses[index],
                (*allocation, amount),
            )

    yield from expand(0, tickets, upper, cutoff, ())


def make_state(counts: CountVector) -> r7.ResidualJointState:
    profiles = r5.anchor_incidence_profiles()
    constructor_api = "_make_state"
    constructor = getattr(r7, constructor_api)
    return cast(r7.ResidualJointState, constructor(counts, profiles, r6.local_losses(profiles)))


def signature(state: r7.ResidualJointState) -> tuple[object, ...]:
    signature_api = "_state_signature"
    return cast(tuple[object, ...], getattr(r7, signature_api)(state))


@dataclass(frozen=True)
class Member:
    state: r7.ResidualJointState
    vectors: tuple[CountVector, ...]

    @property
    def raw_bound(self) -> int:
        return r14.raw_bound(self.state)


@cache
def project_region() -> tuple[Member, ...]:
    verify_sources()
    r7_result = stored(R7_RELATIVE)
    frontier = r7_result["S2_S3_FRONTIER"]
    target = next(i for i, p in enumerate(frontier) if p["JOINT_S2"] == S2_MIN)
    if (
        frontier[target]["MAXIMUM_JOINT_S3"] != S3_UPPER
        or frontier[target - 1]["MAXIMUM_JOINT_S3"] != S3_LOWER
        or r7_result["LOCAL_LOSS_CENSUS_CUTOFF"] != r7.JOINT_LOCAL_LOSS_CUTOFF
    ):
        raise AssertionError("R7 disjoint owner region/window mismatch")
    profiles = r5.anchor_incidence_profiles()
    baseline_s3 = 18 * profiles[0].triple_recovery
    weights = tuple(p.triple_recovery - profiles[0].triple_recovery for p in profiles)
    args = (
        weights,
        r6.local_losses(profiles),
        18,
        S3_LOWER + 1 - baseline_s3,
        S3_UPPER - baseline_s3,
        r7.JOINT_LOCAL_LOSS_CUTOFF,
    )
    first, second = tuple(ascending_vectors(*args)), tuple(descending_vectors(*args))
    if (
        len(set(first)) != len(first)
        or len(set(second)) != len(second)
        or set(first) != set(second)
    ):
        raise AssertionError("two enumerators disagree on projection completeness")
    grouped: dict[tuple[object, ...], list[CountVector]] = {}
    for counts in first:
        if not r6.aggregate_count_vector_is_feasible(counts):
            continue  # R6 necessary relaxation only; no missing-witness inference.
        state = make_state(counts)
        if not S3_LOWER < state.joint_s3 <= S3_UPPER or state.joint_s2 < S2_MIN:
            continue
        owner = next(
            p
            for p in frontier
            if p["JOINT_S2"] <= state.joint_s2 and p["MAXIMUM_JOINT_S3"] >= state.joint_s3
        )
        if owner != frontier[target]:
            raise AssertionError("a projected member belongs to a different R7 owner")
        grouped.setdefault(signature(state), []).append(counts)
    members = tuple(
        sorted(
            (
                Member(
                    replace(make_state(min(vs)), represented_vector_count=len(vs)),
                    tuple(sorted(vs)),
                )
                for vs in grouped.values()
            ),
            key=lambda m: (
                m.state.joint_s2,
                m.state.joint_s3,
                m.state.local_loss,
                m.state.witness_counts,
            ),
        )
    )
    region_digest = digest(tuple((m.state.witness_counts, m.raw_bound) for m in members))
    if (
        len(members) != 214
        or sum(len(m.vectors) for m in members) != 221
        or region_digest != REGION_SHA256
        or sorted(len(m.vectors) for m in members) != [1] * 207 + [2] * 7
        or max(m.raw_bound for m in members) != START_STATE_BOUND
    ):
        raise AssertionError("region digest/count/compression completeness mismatch")
    for member in members:
        if any(signature(make_state(v)) != signature(member.state) for v in member.vectors):
            raise AssertionError("compressed-member signature is not sound")
    return members


def top_band(members: tuple[Member, ...]) -> tuple[Member, ...]:
    band = tuple(m for m in members if m.raw_bound > TOP_THRESHOLD)
    if len(band) != 16:
        raise AssertionError("top-band omission or unexpected membership")
    return band


def support_record(vector: CountVector) -> dict[str, Any]:
    support = r12.construct_support_witness(vector)
    if support is None or not r8.validate_support_assignment(vector, support):
        raise AssertionError("support witness identity/legality failed")
    return {"counts": sparse(vector), "support_witness": support, "support_sha256": digest(support)}


def certify_member(member: Member) -> dict[str, Any]:
    state = member.state
    moments = [r14.moment_certificate(v) for v in member.vectors]
    rational = min(int(row["correction_lower_bound"]) for row in moments)
    applied = state.applied_residual_union_penalty
    correction = max(applied, rational)
    uncorrected = r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    return {
        "member": r24.member_record(state),
        "represented_vectors": [sparse(v) for v in member.vectors],
        "vector_certificates": moments,
        "support_witnesses": [support_record(v) for v in member.vectors],
        "joint_constant": r14.joint_constant(),
        "uncorrected_anchor_bound": uncorrected,
        "prior_applied_correction": applied,
        "minimum_vector_rational_correction": rational,
        "member_certified_correction": correction,
        "correction_combination": COMBINATION,
        "member_raw_bound": member.raw_bound,
        "member_prior_bound": member.raw_bound,
        "member_new_bound": uncorrected - correction,
        "member_drop": correction - applied,
        "region_sha256": REGION_SHA256,
    }


def check_certificate(record: dict[str, Any], member: Member) -> None:
    moments = cast(list[dict[str, Any]], record["vector_certificates"])
    expected_vectors = [sparse(v) for v in member.vectors]
    if (
        record["member"] != normalized(r24.member_record(member.state))
        or record["represented_vectors"] != expected_vectors
        or [row["counts"] for row in moments] != expected_vectors
        or [row["counts"] for row in record["support_witnesses"]] != expected_vectors
    ):
        raise AssertionError("certificate member/vector coverage mismatch")
    for vector, moment, witness in zip(
        member.vectors, moments, record["support_witnesses"], strict=True
    ):
        if (
            moment != normalized(r14.moment_certificate(vector))
            or moment["multiplicity_dual"] != [1, 9]
            or moment["multiplicity_cap"] != 18
            or int(moment["correction_lower_bound"])
            != -(-2 * int(moment["residual_s2_lower_bound"]) // 18)
            or any(2 * math.comb(m, 2) > 18 * max(0, m - 1) for m in range(19))
        ):
            raise AssertionError("rational moment replay/dual mismatch")
        support = tuple(tuple(int(label) for label in row) for row in witness["support_witness"])
        if (
            not r8.validate_support_assignment(vector, support)
            or witness["support_sha256"] != digest(support)
            or witness != normalized(support_record(vector))
        ):
            raise AssertionError("support witness identity/legality failed")
    applied = max(member.state.residual_pair_union_penalty, member.state.complementary_forest_floor)
    rational = min(int(row["correction_lower_bound"]) for row in moments)
    uncorrected = r14.joint_constant() - member.state.anchor_pair_s2 + member.state.anchor_triple_s3
    if (
        member.state.applied_residual_union_penalty != applied
        or member.raw_bound != uncorrected - applied
        or record["joint_constant"] != r14.joint_constant()
        or record["uncorrected_anchor_bound"] != uncorrected
        or record["prior_applied_correction"] != applied
        or record["minimum_vector_rational_correction"] != rational
        or record["member_certified_correction"] != max(applied, rational)
        or record["member_raw_bound"] != member.raw_bound
        or record["member_prior_bound"] != member.raw_bound
        or record["member_new_bound"] != uncorrected - max(applied, rational)
        or record["member_drop"] != max(applied, rational) - applied
        or record["correction_combination"] != COMBINATION
        or record["region_sha256"] != REGION_SHA256
    ):
        raise AssertionError("correction arithmetic/double credit failed")


def recompute_state(
    members: tuple[Member, ...], records: list[dict[str, Any]]
) -> dict[CountVector, int]:
    expected = [sparse(m.state.witness_counts) for m in top_band(members)]
    if [r["member"]["witness_counts"] for r in records] != expected:
        raise AssertionError("top-band omission/duplicate/order mismatch")
    bounds = {m.state.witness_counts: m.raw_bound for m in members}
    ledger = {m.state.witness_counts: m for m in members}
    for record in records:
        key = dense(record["member"]["witness_counts"])
        check_certificate(record, ledger[key])
        bounds[key] = int(record["member_new_bound"])
    return bounds


def build_result() -> dict[str, Any]:
    pins = verify_sources()
    base, r24_result = stored(BASE_RELATIVE), stored(R24_RELATIVE)
    members = project_region()
    band = top_band(members)
    carried = r24.carried_member_certificates(STATE_ID)
    if carried or any(r["owner_id"] == STATE_ID for r in r24_result["STATE_OWNER_CERTIFICATES"]):
        raise AssertionError("target member already carries a rational correction")
    terms = cast(list[dict[str, Any]], base["FINAL_STATE_TERMS"])
    if (
        len(terms) != 23
        or len({r["stable_id"] for r in terms}) != 23
        or [r["bound"] for r in terms if r["stable_id"] == STATE_ID] != [START_STATE_BOUND]
        or [r["bound"] for r in r24_result["CURRENT_STATE_TERMS"] if r["stable_id"] == STATE_ID]
        != [START_STATE_BOUND]
    ):
        raise AssertionError("base/R24 target State authority mismatch")
    records = normalized([certify_member(m) for m in band])
    bounds = recompute_state(members, records)
    remainder = [m for m in members if m not in band]
    final, top_max = max(bounds.values()), max(bounds[m.state.witness_counts] for m in band)
    remainder_max = max(m.raw_bound for m in remainder)
    if (final, top_max, remainder_max) != (
        EXPECTED_STATE_BOUND,
        EXPECTED_TOP_MAX,
        EXPECTED_STATE_BOUND,
    ):
        raise AssertionError("research values do not reproduce independently")
    others = sorted(
        (r for r in terms if r["stable_id"] != STATE_ID), key=lambda r: -int(r["bound"])
    )
    if base["FINAL_R3_FAMILY_BOUND"] != 355_722_668 or base["FINAL_OWNER_IDS"] != [
        others[0]["stable_id"]
    ]:
        raise AssertionError("base family maximum/competing owner mismatch")
    return normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS_STATE_LOCAL_SELF_CHECK_ONLY",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "R24_SOURCE": R24_SOURCE,
            "R24_TREE": R24_TREE,
            "UPSTREAM_FINGERPRINTS_SHA256": pins,
            "SOURCE_PROVENANCE_STATUS": "PASS",
            "CANONICAL_PRIMITIVES": r24.canonical_primitives(),
            "STATE_ID": STATE_ID,
            "TARGET_REGION": {
                "S2_MIN": S2_MIN,
                "S3_LOWER_EXCLUSIVE": S3_LOWER,
                "S3_UPPER_INCLUSIVE": S3_UPPER,
                "R7_LOCAL_LOSS_MAX": r7.JOINT_LOCAL_LOSS_CUTOFF,
            },
            "REGION_DOMAIN": "R7_CENSUS_DOMAIN_ONLY_ABOVE_CUTOFF_REMAINS_IN_CARRIED_TAIL",
            "REGION_SHA256": REGION_SHA256,
            "REGION_COMPLETENESS_STATUS": "PASS_TWO_EXACT_ENUMERATORS",
            "COMPRESSED_MEMBER_COUNT": len(members),
            "REPRESENTED_VECTOR_COUNT": sum(len(m.vectors) for m in members),
            "REGION_VECTORS_SHA256": digest(tuple(sorted(v for m in members for v in m.vectors))),
            "COMPRESSION_SIGNATURE": "R7_COMPLETE_STATE_SIGNATURE",
            "TWO_VECTOR_MEMBERS": [
                {
                    "member": r24.member_record(m.state),
                    "represented_vectors": [sparse(v) for v in m.vectors],
                    "support_witnesses": [support_record(v) for v in m.vectors],
                }
                for m in members
                if len(m.vectors) == 2
            ],
            "TOP_THRESHOLD": TOP_THRESHOLD,
            "TOP_BAND_CERTIFIED_COUNT": len(records),
            "NEW_MEMBER_CERTIFICATES": records,
            "TOP_BAND_MAX": top_max,
            "CARRIED_CERTIFIED_MEMBER_COUNT": len(carried),
            "CARRIED_MEMBERS_PRESERVED": True,
            "REMAINDER_MEMBER_COUNT": len(remainder),
            "REMAINDER_MAX": remainder_max,
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member": r24.member_record(m.state),
                    "represented_vectors": [sparse(v) for v in m.vectors],
                    "prior_valid_bound": m.raw_bound,
                    "final_bound": bounds[m.state.witness_counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": START_STATE_BOUND,
            "FINAL_CERTIFIED_STATE_BOUND": final,
            "STATE_DROP": START_STATE_BOUND - final,
            "CORRECTION_COMBINATION": COMBINATION,
            "DUPLICATE_CORRECTIONS": 0,
            "WITNESS_SOUNDNESS_STATUS": "PASS",
            "R3_FAMILY_BOUND_FROM_BASE": base["FINAL_R3_FAMILY_BOUND"],
            "BASE_FAMILY_OWNER_IDS": base["FINAL_OWNER_IDS"],
            "BASE_STATE_TERMS": terms,
            "BASE_FAMILY_MAX_RECOMPUTATION": base["FINAL_FAMILY_MAX_RECOMPUTATION"],
            "BASE_CLASSIFIED_TERMS_SHA256": base["CLASSIFIED_TERMS_SHA256"],
            "NEXT_COMPETING_OWNER": others[0],
            "PACKET_COMPETING_STATE_THRESHOLD": TOP_THRESHOLD,
            "PACKET_COMPETING_STATE_IDS": [
                r["stable_id"] for r in terms if r["bound"] == TOP_THRESHOLD
            ],
            "R3_FAMILY_AUTHORITY_UNCHANGED": True,
            "R3_CLAIM": "NONE_STATE_LOCAL_CERTIFICATE_ONLY",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "HUNTER_CORRECTIONS_APPLIED": 0,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":")) + "\n"


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    bounds = recompute_state(project_region(), result["NEW_MEMBER_CERTIFICATES"])
    if result["FINAL_CERTIFIED_STATE_BOUND"] != max(bounds.values()):
        raise AssertionError("wrong State maximum")
    if encode(result) != encode(build_result()):
        raise AssertionError("result does not completely reproduce")
    return {"status": "PASS", "certified_members": 16, "state_bound": max(bounds.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    options = parser.parse_args()
    if options.verify:
        result = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
        print(json.dumps(verify_result(result)))
    else:
        result = build_result()
        if not options.no_write:
            RESULT_PATH.write_text(encode(result), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if not isinstance(v, (dict, list))}))


if __name__ == "__main__":
    main()
