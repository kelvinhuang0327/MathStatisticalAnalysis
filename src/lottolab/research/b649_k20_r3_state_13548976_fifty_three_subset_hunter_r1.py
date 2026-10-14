"""Certify all 53 State13548976 members above the sealed Classified maximum.

Adopt only immutable H11/TS-106/H0 inputs at f8bb2f27. Recover the whole
1427-member/1543-vector ledger and select targets by their current bound.
For each vector consider its full multiset and every one-event deletion.
TS-106 supplies exact residual pair counts, balanced four-cell collision
floors and complete nested-threshold Hunter minima for the chosen 17/18
events. Pair completeness and subset applicability are checked here as well.

Smoothing proves the balanced collision lower bound universally. A threshold
graph with component ranks r_j has e <= sum C(r_j+1,2) <= C(sum r_j+1,2).
Descending Kruskal spans every nested threshold graph simultaneously. For
any outcome present in k tree vertices, at most k-1 tree edges are present;
summing proves Hunter's inequality. A subset tree extends to all 18 residual
events by attaching omitted vertices with nonnegative intersection weights.
Concrete legal witnesses illustrate applicability, never universality.

Replace correction by MAX, subtract once, then maximize over all represented
vectors and all State/Classified/Tail terms. No other worktree, census, heavy
solver, or official-outcome enumeration is used.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_12692531_top_band_eleven_event_hunter_r1 as h11

prior = h11.prior
hunter, catalog, six, r24 = prior.hunter, prior.catalog, prior.six, prior.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
type Cells = tuple[int, int, int, int]
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_13548976_FIFTY_THREE_SUBSET_HUNTER_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13548976-fifty-three-subset-hunter-r1"
BASE_HEAD = "f8bb2f27e0c02af819588c0f923a5f883b0f9a0d"
BASE_TREE = "810dffc9f83b5bbc4bf0fbe023c504e75bc152c8"
BASE_RESULT_SHA256 = "31f1b558447ed4b630f55bc49e7955bb395f4eff3a19d41da5041acfad045816"
TARGET_STATE_ID = "state:s2-13548976-s3-951748"
REGION_SHA256 = "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
TARGET_CUTOFF = 355145504
RESIDUAL_EVENT_DEFINITION = prior.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, SUBSET_HUNTER); SUBTRACT_ONCE"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-13548976-fifty-three-subset-hunter-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *h11.source_paths(),
                str(Path(h11.__file__).resolve().relative_to(REPO_ROOT)),
                h11.RESULT_RELATIVE,
            }
        )
    )


def verify_source_authority() -> dict[str, Any]:
    """Bind every executing donor and sealed input, even after caches are warm."""
    prefix = ["git", "-C", str(REPO_ROOT)]
    identity = subprocess.check_output(
        [*prefix, "show", "-s", "--format=%H %T", BASE_HEAD], text=True
    ).strip()
    blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{h11.RESULT_RELATIVE}"])
    if identity != f"{BASE_HEAD} {BASE_TREE}" or sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("immutable BASE_HEAD/TREE/result SHA authority failed")
    if subprocess.run([*prefix, "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"]).returncode:
        raise AssertionError("checkout does not descend from the immutable base")
    fingerprints: dict[str, str] = {}
    for relative in source_paths():
        frozen = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{relative}"])
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"immutable executing source or sealed input changed: {relative}")
        fingerprints[relative] = sha256(frozen).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_sha256": fingerprints,
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    verify_source_authority()
    results = {
        name: cast(dict[str, Any], json.loads(module.RESULT_PATH.read_bytes()))
        for name, module in (("H11", h11), ("TS106", prior), ("H0", prior.h0))
    }
    current, ts = results["H11"], results["TS106"]
    if (
        current["TASK_ID"] != h11.TASK_ID
        or current["FINAL_COMPLETE_R3_UB"] != 355274472
        or ts["TASK_ID"] != prior.TASK_ID
        or (ts["TARGET_MEMBER_COUNT"], ts["TARGET_VECTOR_COUNT"]) != (106, 116)
        or current["TS106_CERTIFICATE_SHA256"] != sha256(prior.RESULT_PATH.read_bytes()).hexdigest()
        or current["TS106_CERTIFICATE_SHA256"] != h11.BASE_RESULT_SHA256
        or dict((r["stable_id"], r["bound"]) for r in current["FINAL_STATE_TERMS"])[TARGET_STATE_ID]
        != 355269698
    ):
        raise AssertionError("sealed H11/TS106 predecessor identity failed")
    return results


def region_authority() -> dict[str, Any]:
    """H11 changes another State; this State's latest complete ledger is TS-106."""
    regions = [r for r in source_results()["TS106"]["REGIONS"] if r["state_id"] == TARGET_STATE_ID]
    if len(regions) != 1 or regions[0]["region_sha256"] != REGION_SHA256:
        raise AssertionError("exact latest State ledger authority failed")
    return cast(dict[str, Any], regions[0])


def region_rows() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], region_authority()["complete_region_members"])


@cache
def region_members() -> tuple[LedgerMember, ...]:
    members = tuple(
        LedgerMember(
            dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in region_rows()
    )
    if (
        len(members) != 1427
        or len({m.counts for m in members}) != 1427
        or sum(m.represented_vector_count for m in members) != 1543
        or catalog.region_fingerprint(members) != REGION_SHA256
        or max(m.final_bound for m in members) != 355269698
        or any(m.final_bound > m.raw_bound or m.represented_vector_count < 1 for m in members)
    ):
        raise AssertionError("complete 1427-member/1543-vector region identity failed")
    return members


def target_members(members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    """Recover all targets from the complete ledger, with no handwritten ID filter."""
    targets = tuple(m for m in members if m.final_bound > TARGET_CUTOFF)
    if (
        TARGET_CUTOFF != 355145504
        or len(targets) != 53
        or sum(m.represented_vector_count for m in targets) != 53
        or any(m.represented_vector_count != 1 for m in targets)
    ):
        raise AssertionError("exact 53-member/53-vector target selection failed")
    highest = sorted(members, key=lambda m: (-m.final_bound, m.counts))[:12]
    if len(highest) != 12 or not {m.counts for m in highest} <= {m.counts for m in targets}:
        raise AssertionError("all twelve highest members must be in the target cohort")
    return targets


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vs in recovered.values() for v in vs]
    if set(recovered) != {m.counts for m in members} or len(flat) != len(set(flat)):
        raise AssertionError("complete represented-vector recovery failed")
    if len(flat) != 1543:
        raise AssertionError("complete represented-vector cardinality failed")
    for member, row in zip(members, region_rows(), strict=True):
        vectors = recovered[member.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        if (
            len(vectors) != member.represented_vector_count
            or tuple(sorted(vectors)) != vectors
            or min(vectors) != member.counts
            or row["member_id"] != member_id(member.counts)
            or row["compression_signature"] != catalog.normalized(signature)
            or vectors != tuple(dense(v) for v in row["represented_vectors"])
        ):
            raise AssertionError("canonical member or compression signature/cardinality failed")
        for vector in vectors:
            rebuilt = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            if (
                len(vector) != 30
                or any(type(c) is not int or c < 0 for c in vector)
                or sum(vector) != 18
                or hunter.eleven.compression_signature(rebuilt) != signature
            ):
                raise AssertionError("represented-vector compression signature failed")
    return recovered


def validate_subset(v: CountVector, u: CountVector) -> None:
    if (
        len(v) != 30
        or len(u) != 30
        or any(type(c) is not int or c < 0 for c in (*u, *v))
        or sum(v) != 18
        or sum(u) not in (17, 18)
        or any(a > b for a, b in zip(u, v, strict=True))
    ):
        raise AssertionError("selected subset must be integer 0<=u<=v with 17/18 events")


def subset_candidates(v: CountVector) -> tuple[CountVector, ...]:
    candidates = (
        v,
        *(tuple(c - int(i == j) for i, c in enumerate(v)) for j, count in enumerate(v) if count),
    )
    for u in candidates:
        validate_subset(v, u)
    return candidates


def select_subset(v: CountVector) -> CountVector:
    candidates = subset_candidates(v)
    u = prior.select_subset(v)
    validate_subset(v, u)
    if u not in candidates:
        raise AssertionError("selected subset is outside the full-or-delete-one candidates")
    return u


@cache
def subset_proof(u: CountVector) -> dict[str, Any]:
    """Adopt the proven primitive and check complete type-pair applicability."""
    if len(u) != 30 or any(type(c) is not int or c < 0 for c in u) or sum(u) not in (17, 18):
        raise AssertionError("selected subset requires integer counts and 17/18 events")
    proof = prior.subset_proof(u)
    pairs = tuple(sorted(six.occupied_type_pairs(u)))
    rows = prior.pair_rows(u)
    if proof["occupied_type_pairs"] != [list(p) for p in pairs]:
        raise AssertionError("occupied type-pair coverage failed")
    for pair in pairs:
        left, right = (hunter.type_cells(i) for i in pair)
        expected = {
            cells
            for cells in product(
                *(
                    range(max(0, a + b - len(labels)), min(a, b) + 1)
                    for a, b, labels in zip(left, right, hunter.CELL_LABELS, strict=True)
                )
            )
            if sum(cells) <= 3
        }
        actual = [r for r in rows if r[:2] == pair]
        if len(actual) != len(expected) or {r[2:6] for r in actual} != expected:
            raise AssertionError("exact type-pair row completeness failed")
        for row in actual:
            cells = row[2:6]
            if six.residual_pair_intersection(*pair, cells) != row[6] or row[6] < 0:
                raise AssertionError("exact residual type-pair intersection failed")
    phi = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(phi, rows)
    incidences = hunter.cell_incidences(u)
    collision = tuple(
        (len(labels) - r) * comb(q, 2) + r * comb(q + 1, 2)
        for total, labels in zip(incidences, hunter.CELL_LABELS, strict=True)
        for q, r in [divmod(total, len(labels))]
    )
    minimum = prior.threshold_minimum(phi, sum(collision), sum(u))
    if (
        proof["pair_rows"] != catalog.normalized(rows)
        or proof["pair_floors"] != list(phi)
        or proof["cell_incidences"] != list(incidences)
        or proof["cell_collision_floors"] != list(collision)
        or proof["collision_mass_floor"] != sum(collision)
        or any(proof[k] != value for k, value in minimum.items())
        or proof["event_count"] != sum(u)
        or proof["selected_subset_counts"] != sparse(u)
        or proof["residual_event_definition"] != RESIDUAL_EVENT_DEFINITION
        or hunter.family_pair_overlap_ceiling() != 3
        or hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or proof["proof_id"] != digest(u)
    ):
        raise AssertionError("exact pair/collision/complete Hunter threshold proof failed")
    return proof


@cache
def sealed_vector_bounds() -> dict[CountVector, tuple[int, ...]]:
    """Keep all immutable per-vector bounds, including TS-106 and H11."""
    found: dict[CountVector, list[int]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            row = cast(dict[str, Any], value)
            if "counts" in row and "vector_new_bound" in row:
                found.setdefault(dense(row["counts"]), []).append(int(row["vector_new_bound"]))
            for child in row.values():
                visit(child)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child)

    for relative in source_paths():
        if relative.endswith(".json"):
            visit(json.loads((REPO_ROOT / relative).read_bytes()))
    return {v: tuple(bounds) for v, bounds in found.items()}


def certify_vector(member: LedgerMember, v: CountVector) -> dict[str, Any]:
    if (
        member not in target_members(region_members())
        or v not in represented_vectors()[member.counts]
    ):
        raise AssertionError("target member or represented-vector membership failed")
    u = select_subset(v)
    proof = subset_proof(u)
    state = catalog.rebuild_member(replace(member, counts=v, represented_vector_count=1))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    prior_bound = min((member.final_bound, *sealed_vector_bounds().get(v, ())))
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior_bound,
    }
    existing = hunter.combine_corrections(credits)
    credits["SUBSET_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(credits)
    bound = min(prior_bound, uncorrected - combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or min(credits.values()) < 0
        or existing != uncorrected - prior_bound
        or combined != max(credits.values())
        or bound != hunter.member_bound(uncorrected, combined)
        or bound >= member.final_bound
    ):
        raise AssertionError("MAX-only single replacement or existing credit preservation failed")
    # Every applicable carried witness remains legal and can use the same
    # universal subset theorem; preserve its bytes rather than replacing it.
    earlier_supports = prior.sealed_vector_rows().get(v, ())
    for row in earlier_supports:
        support = tuple(tuple(int(x) for x in ticket) for ticket in row["support_witness"])
        if not hunter.r8.validate_support_assignment(v, support):
            raise AssertionError("applicable predecessor legal witness is unsound")
    witness = prior.witness_analysis(v, u, proof)
    return catalog.normalized(
        {
            "vector_id": member_id(v),
            "counts": sparse(v),
            "compression_signature": hunter.eleven.compression_signature(state),
            "selected_subset_counts": sparse(u),
            "proof_id": digest(u),
            "candidate_subsets": [
                {
                    "counts": sparse(c),
                    "event_count": sum(c),
                    "rank_relaxation_floor": prior.rank_minimum(
                        prior.subset_parameters(c)[1], sum(prior.subset_parameters(c)[3]), sum(c)
                    ),
                }
                for c in subset_candidates(v)
            ],
            "anchor_union": hunter.anchor_union_size(),
            "residual_event_sum": residual,
            "uncorrected_anchor_bound": uncorrected,
            "corrections": credits,
            "existing_applied_credit": uncorrected - member.final_bound,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_prior_bound": prior_bound,
            "vector_new_bound": bound,
            "preserved_legal_witness_count": len(earlier_supports),
            "witness_analysis": witness,
        }
    )


def certify_member(member: LedgerMember, vectors: tuple[CountVector, ...]) -> dict[str, Any]:
    if vectors != represented_vectors()[member.counts]:
        raise AssertionError("complete represented-vector member coverage failed")
    rows = [certify_vector(member, v) for v in vectors]
    bound = max(int(r["vector_new_bound"]) for r in rows)
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in rows))
    if len(rows) != member.represented_vector_count or correction != min(
        int(r["combined_correction"]) for r in rows
    ):
        raise AssertionError("compressed member must MAX all represented-vector safe bounds")
    return {
        "member_id": member_id(member.counts),
        "witness_counts": sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [sparse(v) for v in vectors],
        "member_prior_bound": member.final_bound,
        "member_raw_bound": member.raw_bound,
        "member_certified_correction": correction,
        "member_new_bound": bound,
        "vector_certificates": rows,
        "correction_combination": CORRECTION_COMBINATION,
    }


def recompute_family(state_bound: int) -> dict[str, Any]:
    source = source_results()["H11"]
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )
    tail = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or TARGET_STATE_ID not in dict(states)
        or len(classified) != source["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or max(b for _, b in classified) != source["CLASSIFIED_MAX"]
        or source["CLASSIFIED_MAX"] != TARGET_CUTOFF
        or tail != source["TAIL_BOUND"]
        or tail != 354039277
        or start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or start["R3_BOUND"] != 355274472
    ):
        raise AssertionError("complete H11 State/Classified/Tail authority failed")
    updated = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    if final["R3_BOUND"] != 355274472 or final["OWNER_IDS"] != [h11.TARGET_STATE_ID]:
        raise AssertionError("standalone Family maximum or owner failed")
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "classified_max": max(b for _, b in classified),
        "tail": tail,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    members, vectors = region_members(), represented_vectors()
    targets = target_members(members)
    records = [certify_member(m, vectors[m.counts]) for m in targets]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    target_counts = {m.counts for m in targets}
    remainder = tuple(m for m in members if m.counts not in target_counts)
    cohort_max = max(r["member_new_bound"] for r in records)
    if (
        {v for v in priors if bounds[v] != priors[v]} != target_counts
        or any(bounds[m.counts] != m.final_bound for m in remainder)
        or len(remainder) != 1374
        or sum(len(vectors[m.counts]) for m in remainder) != 1490
        or max(bounds[m.counts] for m in remainder) != 355116818
        or cohort_max != 353607184
        or max(bounds.values()) != 355116818
        or r24.INCUMBENT != 313263888
    ):
        raise AssertionError("exact cohort maximum, preserved remainder or State bound failed")
    family = recompute_family(max(bounds.values()))
    subsets = {
        dense(row["selected_subset_counts"]) for r in records for row in r["vector_certificates"]
    }
    top12 = sorted(members, key=lambda m: (-m.final_bound, m.counts))[:12]
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_EXECUTING_BYTES",
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_MEMBER_COVERAGE": len(members),
            "REGION_VECTOR_COVERAGE": sum(len(v) for v in vectors.values()),
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "TARGET_SELECTION": "current_final_bound > 355145504; COMPLETE_SEALED_LEDGER",
            "TARGET_MEMBER_COUNT": len(records),
            "TARGET_VECTOR_COUNT": sum(r["represented_vector_count"] for r in records),
            "TOP_TWELVE_MEMBER_IDS": [member_id(m.counts) for m in top12],
            "COMPRESSED_VECTOR_STATUS": "PASS_ALL_1543_SIGNATURES_AND_53_SINGLE_VECTOR_TARGETS",
            "SELECTED_SUBSET_VALIDITY": "PASS_INTEGER_0_LE_U_LE_V_17_OR_18_EVENTS",
            "SUBSET_SELECTION_RULE": (
                "FULL_VECTOR_OR_EACH_OCCUPIED_TYPE_DELETE_ONE; GLOBAL_BEST_NOT_REQUIRED"
            ),
            "SUBSET_PROOFS": [subset_proof(u) for u in sorted(subsets)],
            "EXACT_PAIR_FLOOR_STATUS": "PASS_COMPLETE_TYPE_PAIRS_AND_EXACT_RESIDUAL_FLOORS",
            "COLLISION_FLOOR_STATUS": "PASS_BALANCED_INTEGER_FREQUENCIES_IN_FOUR_CELLS",
            "HUNTER_THRESHOLD_STATUS": "PASS_COMPLETE_NESTED_THRESHOLD_INTEGER_MINIMA",
            "TREE_EXTENSION_STATUS": "PASS_UNIVERSAL_HUNTER_AND_NONNEGATIVE_FULL_TREE_EXTENSION",
            "MEMBER_CERTIFICATES": records,
            "NEW_TARGET_COHORT_MAX": cohort_max,
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_REMAINDER_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in remainder)
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
            "PREDECESSOR_CERTIFICATE_PRESERVATION": "PASS_TS106_H0_H11_BYTE_SEALS_AND_MAX_CREDITS",
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in authority["upstream_sha256"].items() if p.endswith(".json")
            },
            "COMPLETE_REGION_MEMBERS": [
                {**row, "prior_bound": m.final_bound, "final_bound": bounds[m.counts]}
                for m, row in zip(members, region_rows(), strict=True)
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_TARGET_STATE_UB": max(bounds.values()),
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "STATE_TERM_COUNT": len(family["states"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS_ALL_STATES_ALL_CLASSIFIED_TERMS_AND_TAIL",
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_MAX": family["classified_max"],
            "TAIL_BOUND": family["tail"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_STANDALONE_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_SUBTRACTION",
            "WITNESS_SOUNDNESS_STATUS": (
                "PASS_53_LEGAL_SUPPORTS_AND_APPLICABLE_PREDECESSOR_WITNESSES"
            ),
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    targets = target_members(region_members())
    records = result["MEMBER_CERTIFICATES"]
    if [r["member_id"] for r in records] != [member_id(m.counts) for m in targets]:
        raise AssertionError("exact 53 target member certificate coverage failed")
    proofs = {p["proof_id"]: p for p in result["SUBSET_PROOFS"]}
    for record, member in zip(records, targets, strict=True):
        vectors = represented_vectors()[member.counts]
        rows = record["vector_certificates"]
        if (
            record["represented_vectors"] != [sparse(v) for v in vectors]
            or len(rows) != len(vectors)
            or record["represented_vector_count"] != len(vectors)
        ):
            raise AssertionError("complete represented-vector coverage failed")
        for row, vector in zip(rows, vectors, strict=True):
            u = dense(row["selected_subset_counts"])
            validate_subset(vector, u)
            if row["counts"] != sparse(vector) or row["proof_id"] not in proofs:
                raise AssertionError("represented-vector or subset proof identity failed")
            if encode(proofs[row["proof_id"]]) != encode(subset_proof(u)):
                raise AssertionError("exact pair/collision/Hunter proof replay failed")
            if row["combined_correction"] != max(row["corrections"].values()) or row[
                "vector_new_bound"
            ] != min(
                row["vector_prior_bound"],
                row["uncorrected_anchor_bound"] - row["combined_correction"],
            ):
                raise AssertionError("corrections must use MAX and one subtraction, never SUM")
        if record["member_new_bound"] != max(r["vector_new_bound"] for r in rows):
            raise AssertionError("compressed member must MAX all represented-vector bounds")
    if encode(result) != encode(build_result()):
        raise AssertionError("stored result differs from complete exact certificate replay")
    return {
        "status": "PASS",
        "members": 53,
        "vectors": 53,
        "region_members": 1427,
        "region_vectors": 1543,
        "state_terms": 23,
    }


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from byte-exact replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "NEW_TARGET_COHORT_MAX",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_TARGET_STATE_UB",
        "FINAL_STANDALONE_COMPLETE_R3_UB",
        "FINAL_OWNER",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
