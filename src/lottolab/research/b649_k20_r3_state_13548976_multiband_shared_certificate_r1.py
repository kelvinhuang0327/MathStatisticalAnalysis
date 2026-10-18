"""One exact residual R14 certificate for four consecutive R3 bands.

Reconstruct the common occupied-pair table, specialize by exact multiplicity,
and derive the outside dual from each vector's occupied rows. The (5,5) pair
vanishes at t=5, so its limiting slope must not be carried across that boundary.
Replay every inherited certificate and the complete region/23-State Family;
replace only eight bounds by a single maximum correction. No solver or census.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from fractions import Fraction
from functools import cache
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13548976_next_two_r14_certificate_r1 as prior

base, region, hunter = prior.base, prior.region, prior.hunter
six, catalog, r14, r8 = prior.six, prior.catalog, prior.r14, prior.r8
CountVector = tuple[int, ...]
LedgerMember = catalog.LedgerMember
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_13548976_MULTIBAND_SHARED_CERTIFICATE_IMPLEMENT_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13548976-multiband-shared-certificate-implement-r1"
BASE_HEAD = "3ad0f1b26d69b25c9c065c1d9ed8b7816f0350bd"
BASE_TREE = "44d4edfd92703db5822e1c6a5e765ceb813e9dd4"
BASE_RESULT_SHA256 = "bc69e67f5c85911b8eba9857ab933984eb27d28c3e3badfdd46bec59141687c1"
BASE_MODULE_SHA256 = "636cc4c9367eac3f01107ce62ca8035bc09e3bd5b702fbd49939d0e75041d71c"
TARGET_STATE_ID = prior.TARGET_STATE_ID
REGION_SHA256 = prior.REGION_SHA256
PARAMETERS = tuple((t, j) for t in range(2, 6) for j in (4, 1))
TARGET_VECTORS = tuple(dense([[0, 11], [j, 1], [5, 6 - t], [16, t]]) for t, j in PARAMETERS)
TARGET_IDS = tuple(member_id(v) for v in TARGET_VECTORS)
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-13548976-multiband-shared-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    "src/lottolab/research/b649_k20_r3_state_13548976_next_two_r14_certificate_r1.py": (
        BASE_MODULE_SHA256
    ),
}
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_R14, EXISTING_HUNTER, NEW_R14)"


def json_digest(payload: object) -> str:
    """Digest of stored certificates, whose definitions carry non-ASCII set symbols."""

    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def prior_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or stored["FINAL_STATE_MEMBER_IDS"] != list(TARGET_IDS[:2])
        or prior.verify_result(stored)["status"] != "PASS"
    ):
        raise AssertionError("immutable predecessor source identity or replay failed")
    return stored


def current_member_bounds(members: tuple[LedgerMember, ...]) -> dict[CountVector, int]:
    authority = prior_authority()
    earlier = prior.current_member_bounds(members)
    bounds = six.replaced_bounds(earlier, authority["MEMBER_CERTIFICATES"])
    replay = [
        {
            "member_id": member_id(m.counts),
            "witness_counts": sparse(m.counts),
            "represented_vector_count": m.represented_vector_count,
            "raw_bound": m.raw_bound,
            "prior_bound": earlier[m.counts],
            "final_bound": bounds[m.counts],
        }
        for m in members
    ]
    if (
        len(members) != 1427
        or len(set(bounds)) != 1427
        or sum(m.represented_vector_count for m in members) != 1543
        or catalog.region_fingerprint(members) != REGION_SHA256
        or catalog.normalized(replay) != authority["COMPLETE_REGION_MEMBERS"]
    ):
        raise AssertionError("complete region coverage or source bounds failed")
    return bounds


def target_members(
    members: tuple[LedgerMember, ...], bounds: dict[CountVector, int]
) -> tuple[LedgerMember, ...]:
    """Discover the four largest distinct bands from the complete current ledger."""

    if set(bounds) != {m.counts for m in members}:
        raise AssertionError("target member coverage failed")
    levels = sorted(set(bounds.values()), reverse=True)[:4]
    layers = tuple(tuple(m for m in members if bounds[m.counts] == level) for level in levels)
    available = {m.counts: m for layer in layers for m in layer}
    if (
        len(levels) != 4
        or any(len(layer) != 2 for layer in layers)
        or set(available) != set(TARGET_VECTORS)
    ):
        raise AssertionError("exact four-band eight target member identities failed")
    cohort = tuple(available[vector] for vector in TARGET_VECTORS)
    if any(m.represented_vector_count != 1 or bounds[m.counts] != m.raw_bound for m in cohort):
        raise AssertionError("exact four-band eight target member identities failed")
    return cohort


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = six.region_members()
    cohort = target_members(members, current_member_bounds(members))
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in cohort))
    if recovered != {m.counts: (m.counts,) for m in cohort}:
        raise AssertionError("exact target represented-vector coverage failed")
    return recovered


def shared_pair_rows() -> tuple[tuple[int, ...], ...]:
    """Recount the 65-row union by DP, sealed pair tables and inclusion/exclusion."""

    pairs = hunter.occupied_type_pairs(TARGET_VECTORS)
    rows = cast(tuple[tuple[int, ...], ...], hunter.exact_pair_rows(pairs))
    keys = {row[:6] for row in rows}
    if len(rows) != 65 or len(keys) != len(rows):
        raise AssertionError("exact 65-row shared pair table coverage failed")
    for left, right in pairs:
        overlaps = hunter.feasible_cell_overlaps(hunter.type_cells(left), hunter.type_cells(right))
        subset = [row for row in rows if row[:2] == (left, right)]
        if {row[2:6] for row in subset} != set(overlaps):
            raise AssertionError("exact shared pair overlap coverage failed")
        for row in subset:
            if (
                six.residual_pair_intersection(
                    left, right, cast(tuple[int, int, int, int], row[2:6])
                )
                != row[6]
            ):
                raise AssertionError("exact shared residual-event inclusion/exclusion failed")
    return rows


def require_piecewise_slope(vector: CountVector, slope: Fraction) -> None:
    """Require the greatest common outside slope for this exact occupied-pair set."""

    if vector not in TARGET_VECTORS:
        raise AssertionError("residual vector identity failed")
    rows = shared_pair_rows()
    slopes: list[Fraction] = []
    for pair in six.occupied_type_pairs(vector):
        subset = [row for row in rows if row[:2] == pair]
        minimum = min(row[6] for row in subset)
        slopes.extend(Fraction(row[6] - minimum, row[5]) for row in subset if row[5])
        if any(row[6] - minimum < slope * row[5] for row in subset):
            raise AssertionError("piecewise outside slope applicability failed")
    if not slopes or slope != min(slopes):
        raise AssertionError("piecewise outside slope is not exact for occupied pairs")


def exact_moment_certificate(vector: CountVector) -> dict[str, Any]:
    """Specialize the shared table, then independently replay the existing R14 dual."""

    if vector not in TARGET_VECTORS:
        raise AssertionError("residual vector identity failed")
    rows = shared_pair_rows()
    records: list[dict[str, Any]] = []
    minima: int = 0
    s4: int = 0
    pair_total: int = 0
    slopes: list[Fraction] = []
    occupied_pairs = cast(tuple[tuple[int, int], ...], six.occupied_type_pairs(vector))
    for left, right in occupied_pairs:
        exact = tuple(row for row in rows if row[:2] == (left, right))
        table = cast(tuple[tuple[int, ...], ...], r8._pair_event_correction_table(left, right))
        minimum = min(row[6] for row in exact)
        slope = min(Fraction(row[6] - minimum, row[5]) for row in exact if row[5])
        count: int = comb(vector[left], 2) if left == right else vector[left] * vector[right]
        s4_minimum = min(row[5] for row in table)
        pair_total += count
        minima += count * minimum
        s4 += count * s4_minimum
        slopes.append(slope)
        records.append(
            {
                "types": [left, right],
                "pair_count": count,
                "pair_minimum": minimum,
                "outside_slope": [slope.numerator, slope.denominator],
                "s4_minimum": s4_minimum,
                "exact_residual_rows": exact,
            }
        )
    if pair_total != comb(sum(vector), 2) or sum(vector) != 18:
        raise AssertionError("residual pair multiplicities failed")
    slope = min(slopes)
    require_piecewise_slope(vector, slope)
    profiles = catalog.r5.anchor_incidence_profiles()
    outside = sum(n * p.outside for n, p in zip(vector, profiles, strict=True))
    labels = len(hunter.CELL_LABELS[3])
    quotient, remainder = divmod(outside, labels)
    mass = (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
    floor: int = minima + int(prior.prior.ceil_fraction(slope * mass))
    correction = six.ceiling_divide_by_9(floor)
    dual_rows = [[m, comb(m, 2), max(0, m - 1)] for m in range(sum(vector) + 1)]
    if any(Fraction(pairs, 9) > credit for _, pairs, credit in dual_rows):
        raise AssertionError("residual multiplicity dual failed")
    moment = catalog.normalized(
        {
            "counts": sparse(vector),
            "pair_table_rows": records,
            "pair_count_total": pair_total,
            "pair_minimum_sum": minima,
            "outside_slope": [slope.numerator, slope.denominator],
            "outside_incidence_total": outside,
            "outside_label_count": labels,
            "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
            "outside_pair_mass_floor": mass,
            "residual_s2_lower_bound": floor,
            "s4_pairwise_lower_bound": s4,
            "multiplicity_cap": sum(vector),
            "multiplicity_dual": [1, 9],
            "multiplicity_dual_rows": dual_rows,
            "correction_lower_bound": correction,
        }
    )
    if moment != prior.prior.exact_moment_certificate(vector):
        raise AssertionError("independent exact residual moment or integer ceiling failed")
    return cast(dict[str, Any], moment)


def shared_certificate(moments: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive B(t) and Q(t) coefficients from exact moments; check both j at every t."""

    if len(moments) != len(PARAMETERS):
        raise AssertionError("shared certificate requires all eight parameter cases")
    minima = [int(moments[2 * i]["pair_minimum_sum"]) for i in range(4)]
    masses = [int(moments[2 * i]["outside_pair_mass_floor"]) for i in range(4)]
    second = minima[2] - 2 * minima[1] + minima[0]
    quadratic = Fraction(second, 2)
    linear = minima[1] - minima[0] - 5 * quadratic
    constant = minima[0] - 2 * linear - 4 * quadratic
    mass_linear = masses[1] - masses[0]
    mass_constant = masses[0] - 2 * mass_linear
    if any(x.denominator != 1 for x in (constant, linear, quadratic)):
        raise AssertionError("shared exact polynomial is not integral")
    for (t, _j), moment in zip(PARAMETERS, moments, strict=True):
        vector = dense(moment["counts"])
        require_piecewise_slope(vector, Fraction(*moment["outside_slope"]))
        if (
            moment["pair_minimum_sum"] != constant + linear * t + quadratic * t * t
            or moment["outside_pair_mass_floor"] != mass_constant + mass_linear * t
        ):
            raise AssertionError("shared polynomial specialization failed")
    rows = shared_pair_rows()
    return {
        "parameterization": "v(t,j) = [0,11][j,1][5,6-t][16,t]",
        "parameters": PARAMETERS,
        "residual_event_definition": hunter.RESIDUAL_EVENT_DEFINITION,
        "exact_pair_rows": rows,
        "exact_pair_row_count": len(rows),
        "pair_rows_sha256": digest(rows),
        "B_coefficients": [int(constant), int(linear), int(quadratic)],
        "Q_coefficients": [mass_constant, mass_linear],
        "slope_specializations": [
            {
                "t": t,
                "j": j,
                "occupied_pairs": six.occupied_type_pairs(v),
                "outside_slope": m["outside_slope"],
            }
            for (t, j), v, m in zip(PARAMETERS, TARGET_VECTORS, moments, strict=True)
        ],
        "multiplicity_cap": 18,
        "multiplicity_dual": [1, 9],
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], prior_bound: int
) -> dict[str, Any]:
    if (
        member_id(member.counts) not in TARGET_IDS
        or vectors != represented_vectors()[member.counts]
        or prior_bound != member.raw_bound
    ):
        raise AssertionError("target represented-vector coverage or prior bound failed")
    state = catalog.rebuild_member(member)
    records: list[dict[str, Any]] = []
    for vector in vectors:
        current = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
        signature = hunter.eleven.compression_signature(current)
        if signature != hunter.eleven.compression_signature(state):
            raise AssertionError("represented vector compression signature failed")
        moment = exact_moment_certificate(vector)
        floor = int(moment["residual_s2_lower_bound"])
        if int(moment["correction_lower_bound"]) != (floor + 8) // 9:
            raise AssertionError("exact integer ceiling of the residual moment failed")
        nine, eleven = base.nine_event_proof(), base.prior.eleven_event_proof()
        if vector[0] < max(nine["event_count"], eleven["event_count"]):
            raise AssertionError("Hunter selected residual events applicability failed")
        uncorrected = r14.joint_constant() - current.anchor_pair_s2 + current.anchor_triple_s3
        applied = max(current.residual_pair_union_penalty, current.complementary_forest_floor)
        corrections = {
            "R6_PAIR": current.residual_pair_union_penalty,
            "FOREST": current.complementary_forest_floor,
            "EXISTING_R14": max(0, member.raw_bound - prior_bound),
            "EXISTING_HUNTER": max(int(nine["hunter_floor"]), int(eleven["hunter_floor"])),
            "NEW_R14": int(moment["correction_lower_bound"]),
        }
        combined = hunter.combine_corrections(corrections)
        residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector))
        bound = hunter.member_bound(uncorrected, combined)
        if (
            applied != current.applied_residual_union_penalty
            or prior_bound != uncorrected - applied
            or hunter.anchor_union_size() + residual_sum != uncorrected
            or combined != max(corrections.values())
            or bound != uncorrected - combined
            or bound >= prior_bound
        ):
            raise AssertionError("max single correction replacement failed")
        support = hunter.r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("exact support witness failed")
        residual_cost, s4_cost = r8.witness_costs(vector, support)
        if (
            residual_cost < moment["residual_s2_lower_bound"]
            or s4_cost < moment["s4_pairwise_lower_bound"]
        ):
            raise AssertionError("support witness violates the exact moment floor")
        records.append(
            {
                "vector_id": member_id(vector),
                "counts": sparse(vector),
                "compression_signature": signature,
                "moment_certificate": moment,
                "moment_sha256": digest(moment),
                "residual_event_definition": hunter.RESIDUAL_EVENT_DEFINITION,
                "residual_pair_moment": moment["residual_s2_lower_bound"],
                "r14_correction": corrections["NEW_R14"],
                "corrections": corrections,
                "prior_applied_correction": applied,
                "combined_correction": combined,
                "anchor_union": hunter.anchor_union_size(),
                "residual_event_sum": residual_sum,
                "uncorrected_anchor_bound": uncorrected,
                "vector_new_bound": bound,
                "support_witness": support,
                "support_sha256": digest(support),
                "support_residual_pair_moment": residual_cost,
                "support_s4_pair_moment": s4_cost,
                "nine_event_witness_analysis": region.witness_analysis(vector, support, nine),
                "eleven_event_witness_analysis": region.witness_analysis(vector, support, eleven),
            }
        )
    return catalog.normalized(
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "vector_certificates": records,
            "member_prior_bound": prior_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": min(r["combined_correction"] for r in records),
            "member_new_bound": max(r["vector_new_bound"] for r in records),
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def preserved_bounds_sha256(
    members: tuple[LedgerMember, ...], bounds: dict[CountVector, int], changed: set[CountVector]
) -> str:
    """The ordered (witness vector, bound) pairs of every member left untouched."""

    return digest(tuple((m.counts, bounds[m.counts]) for m in members if m.counts not in changed))


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = prior_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    if len(terms) != 23 or len(dict(terms)) != 23 or TARGET_STATE_ID not in dict(terms):
        raise AssertionError("complete 23-State identity failed")
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    if (
        tail != authority["TAIL_BOUND"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or len(classified) != authority["CLASSIFIED_TERM_COUNT"]
        or [{"stable_id": k, "bound": b} for k, b in classified if k == catalog.r24.AGGREGATE_ID]
        != authority["CLASSIFIED_AGGREGATE"]
    ):
        raise AssertionError("preserved classified aggregate or Tail failed")
    start = six.tail.family_maximum(tail, terms, classified)
    if start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("starting complete family differs from source")
    replaced = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in terms)
    return {
        "start": start,
        "final": six.tail.family_maximum(tail, replaced, classified),
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
    }


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    authority = prior_authority()
    members = six.region_members()
    priors = current_member_bounds(members)
    cohort = target_members(members, priors)
    records = [certify_member(m, represented_vectors()[m.counts], priors[m.counts]) for m in cohort]
    bounds = six.replaced_bounds(priors, records)
    changed = {c for c in priors if priors[c] != bounds[c]}
    if changed != {m.counts for m in cohort}:
        raise AssertionError("exactly eight member replacements required")
    final = max(bounds.values())
    family = recompute_family(final)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("target State bound differs from complete region maximum")
    rows = [r["vector_certificates"][0] for r in records]
    common = shared_certificate([row["moment_certificate"] for row in rows])
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "BASE_MODULE_SHA256": BASE_MODULE_SHA256,
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "DONOR_SOURCE_IDENTITIES": {
                **authority["DONOR_SOURCE_IDENTITIES"],
                "NEXT_TWO_R14": {
                    "task_id": prior.TASK_ID,
                    "result_sha256": BASE_RESULT_SHA256,
                    "module_sha256": BASE_MODULE_SHA256,
                },
            },
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
            "EIGHT_MEMBER_IDS": [r["member_id"] for r in records],
            "REPRESENTED_VECTOR_COVERAGE": [r["represented_vector_count"] for r in records],
            "REGION_COVERAGE_STATUS": "PASS_1427_MEMBERS_1543_VECTORS_UNCHANGED",
            "MEMBER_CERTIFICATES": records,
            "COMMON_CERTIFICATE": common,
            "EXACT_PAIR_ROW_STATUS": "PASS_65_EXACT_ROWS_REPLAYED",
            "PIECEWISE_SLOPE_STATUS": "PASS_EXACT_OCCUPIED_PAIRS_PER_VECTOR",
            "EIGHT_MEMBER_COVERAGE": "PASS_8_OF_8",
            "REPRESENTED_VECTOR_COVERAGE_STATUS": "PASS_8_OF_8",
            "FOUR_NEW_BAND_BOUNDS": [r["member_new_bound"] for r in records[::2]],
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in fingerprints.items() if p.endswith(".json")
            },
            "COMPLETE_UPDATED_BOUNDS_SHA256": preserved_bounds_sha256(members, bounds, set()),
            "RESIDUAL_MOMENT_FLOORS": [row["residual_pair_moment"] for row in rows],
            "R14_CORRECTIONS": [row["r14_correction"] for row in rows],
            "EXACT_MOMENT_DIGESTS": [row["moment_sha256"] for row in rows],
            "SUPPORT_DIGESTS": [row["support_sha256"] for row in rows],
            "NEW_MEMBER_BOUNDS": [r["member_new_bound"] for r in records],
            "PRESERVED_MEMBER_COUNT": len(members) - len(changed),
            "PRESERVED_MEMBER_BOUNDS_SHA256": preserved_bounds_sha256(members, bounds, changed),
            "PRESERVED_MEMBER_BOUNDS_STATUS": "PASS_1419_MEMBER_BOUNDS_UNCHANGED",
            "PREVIOUS_MEMBER_CERTIFICATES_SHA256": json_digest(authority["MEMBER_CERTIFICATES"]),
            "PREVIOUS_REGION_CERTIFICATES_SHA256": authority["PREVIOUS_REGION_CERTIFICATES_SHA256"],
            "PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256": authority[
                "PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"
            ],
            "PREVIOUS_CERTIFICATE_STATUS": "PASS_EXACT_SOURCE_REPLAY_AND_PRESERVATION",
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "represented_vector_count": m.represented_vector_count,
                    "raw_bound": m.raw_bound,
                    "prior_bound": priors[m.counts],
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_STATE_BOUND": final,
            "FINAL_STATE_MEMBER_IDS": [member_id(c) for c, b in bounds.items() if b == final],
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
            "TAIL_BOUND": family["tail_bound"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_AGGREGATE": authority["CLASSIFIED_AGGREGATE"],
            "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": catalog.r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - catalog.r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                row["uncorrected_anchor_bound"] - row["vector_new_bound"]
                != max(row["corrections"].values())
                for row in rows
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_EIGHT_EXACT_SUPPORTS_AND_HUNTER_APPLICABILITY",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject mathematical tampering semantically before the final full replay."""

    verify_upstream_fingerprints()
    identity = {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "BASE_MODULE_SHA256": BASE_MODULE_SHA256,
        "STATE_ID": TARGET_STATE_ID,
        "REGION_SHA256": REGION_SHA256,
    }
    if any(result.get(k) != v for k, v in identity.items()):
        raise AssertionError("source identity failed")
    records = result["MEMBER_CERTIFICATES"]
    if tuple(r["member_id"] for r in records) != TARGET_IDS:
        raise AssertionError("exact eight member certificate coverage failed")
    if result["COMMON_CERTIFICATE"] != catalog.normalized(
        shared_certificate([exact_moment_certificate(v) for v in TARGET_VECTORS])
    ):
        raise AssertionError("shared pair table, polynomial or piecewise slope replay failed")
    members = {m.counts: m for m in six.region_members()}
    priors = current_member_bounds(tuple(members.values()))
    for record in records:
        vector = dense(record["witness_counts"])
        expected = certify_member(members[vector], represented_vectors()[vector], priors[vector])
        if (
            record["represented_vectors"] != expected["represented_vectors"]
            or len(record["vector_certificates"]) != record["represented_vector_count"]
        ):
            raise AssertionError("represented-vector certificate coverage failed")
        for row, replay in zip(
            record["vector_certificates"], expected["vector_certificates"], strict=True
        ):
            if (
                row["counts"] != replay["counts"]
                or row["compression_signature"] != replay["compression_signature"]
            ):
                raise AssertionError("represented-vector identity or compression failed")
            if any(
                row[k] != replay[k]
                for k in (
                    "moment_certificate",
                    "moment_sha256",
                    "residual_pair_moment",
                    "r14_correction",
                    "residual_event_definition",
                )
            ):
                raise AssertionError("exact residual moment or integer ceiling failed")
            if any(
                row[k] != replay[k]
                for k in (
                    "corrections",
                    "combined_correction",
                    "prior_applied_correction",
                    "uncorrected_anchor_bound",
                    "vector_new_bound",
                )
            ):
                raise AssertionError("max single correction replacement failed")
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if not r8.validate_support_assignment(vector, support):
                raise AssertionError("stored support witness is invalid")
            if digest(support) != row["support_sha256"]:
                raise AssertionError("stored support witness fingerprint failed")
        if record != expected:
            raise AssertionError("member certificate or witness arithmetic differs from replay")
    replay_result = build_result()
    if any(
        result[k] != replay_result[k]
        for k in (
            "COMPLETE_REGION_MEMBERS",
            "PRESERVED_MEMBER_COUNT",
            "PRESERVED_MEMBER_BOUNDS_SHA256",
            "COMPLETE_UPDATED_BOUNDS_SHA256",
        )
    ):
        raise AssertionError("complete region preservation or member coverage failed")
    if any(
        result[k] != replay_result[k]
        for k in (
            "START_STATE_TERMS",
            "FINAL_STATE_TERMS",
            "FINAL_STATE_MEMBER_IDS",
            "FINAL_FAMILY_MAX_RECOMPUTATION",
            "FINAL_COMPLETE_R3_UB",
            "FINAL_OWNER_IDS",
            "TAIL_BOUND",
            "CLASSIFIED_AGGREGATE",
        )
    ):
        raise AssertionError("complete 23-State family or Tail/aggregate replay failed")
    if result != replay_result:
        raise AssertionError("stored result differs from complete exact replay")
    return {"status": "PASS", "members": 8, "vectors": 8, "region_members": 1427}


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    """Semantic verification plus byte identity of the stored file."""

    stored_bytes = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored_bytes)))
    if stored_bytes != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from the encoded replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "EIGHT_MEMBER_IDS",
        "R14_CORRECTIONS",
        "NEW_MEMBER_BOUNDS",
        "FINAL_STATE_BOUND",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
