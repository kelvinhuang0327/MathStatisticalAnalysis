"""Execute the locked STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1 study.

Reads locked parameters from
`docs/research/matrix-native-results/low-overlap-geometry-mechanism-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (same
fail-closed pattern every prior lock-and-execute script in this Matrix
uses). For each of B649, T539, and P638 Zone-1: builds the canonical Sidon
and Arm-B `k=20` portfolios once (all smaller ladder rungs are exact
prefixes, never rebuilt independently), then makes exactly one streaming
pass over that lottery's complete winning space computing both arms'
winner-multiplicity distributions `N_c` at every ladder rung
simultaneously. Every downstream quantity (`K`, `I`, `COVERED`,
`REDUNDANCY`, `S_j`, the inclusion-exclusion reconstruction, exact `Q`, the
Arm-B-minus-Sidon signed decomposition, and the independent geometry-to-S2
cross-check) is derived from those integer counts -- no winner or
per-winner multiplicity is retained. `MONTE_CARLO: NONE`.
`HISTORICAL_DRAWS: NOT_USED`. `P638_ZONE2`/`ARM_C`: not touched by any
import in this module. Every coverage value is an exact
`fractions.Fraction`; reconstructed `Q` is cross-checked against the
already-sealed source cells before any classification is computed.
"""

from __future__ import annotations

import itertools
import json
import math
import resource
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research.cyclic_sidon_shift import (
    SIDON_BASE_SET_0_INDEXED as _B649_SIDON_BASE,
)
from lottolab.research.cyclic_sidon_shift import (
    sidon_shift_portfolio as _b649_sidon_portfolio,
)
from lottolab.research.cyclic_sidon_shift_p638 import (
    SIDON_BASE_SET_0_INDEXED as _P638_SIDON_BASE,
)
from lottolab.research.cyclic_sidon_shift_p638 import (
    sidon_shift_portfolio as _p638_sidon_portfolio,
)
from lottolab.research.cyclic_sidon_shift_t539 import (
    SIDON_BASE_SET_0_INDEXED as _T539_SIDON_BASE,
)
from lottolab.research.cyclic_sidon_shift_t539 import (
    sidon_shift_portfolio as _t539_sidon_portfolio,
)
from lottolab.research.exact_coverage_baseline import (
    exact_random_portfolio_coverage,
    qualifying_ticket_count,
)
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_min_overlap_constructor_p638_zone1 import (
    greedy_min_overlap_portfolio_p638_zone1,
)
from lottolab.research.greedy_min_overlap_constructor_t539 import (
    greedy_min_overlap_portfolio_t539,
)
from lottolab.research.low_overlap_geometry_mechanism import (
    PortfolioGeometry,
    gain_over_random_ratio_to_sidon,
    portfolio_geometry,
    relative_coverage_delta_vs_sidon,
    relative_lift_vs_random,
    s2_from_ticket_pair_intersection_histogram,
)

Ticket = tuple[int, ...]

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "low-overlap-geometry-mechanism-v1-preregistration-hash.json"
)
MATRIX_RESULTS = Path("docs/research/matrix-native-results")
OUTPUT_PATH = MATRIX_RESULTS / "low-overlap-geometry-mechanism-v1-result.json"

LADDER: tuple[int, ...] = (1, 3, 5, 10, 15, 20)
MAX_K = 20
MINIMUM_MATCHES = 3
LOTTERY_KEYS: tuple[str, ...] = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO_zone1")
LOTTERY_LOCKED_KEY: dict[str, str] = {
    "BIG_LOTTO": "big_lotto",
    "DAILY_539": "daily_539",
    "POWER_LOTTO_zone1": "power_lotto_zone1",
}

CONSTRUCTORS: dict[
    str, tuple[Callable[[int], tuple[Ticket, ...]], Callable[[int], tuple[Ticket, ...]]]
] = {
    "BIG_LOTTO": (_b649_sidon_portfolio, lambda k: greedy_min_overlap_portfolio(49, 6, k)),
    "DAILY_539": (_t539_sidon_portfolio, greedy_min_overlap_portfolio_t539),
    "POWER_LOTTO_zone1": (_p638_sidon_portfolio, greedy_min_overlap_portfolio_p638_zone1),
}
SIDON_BASE_SETS: dict[str, tuple[int, ...]] = {
    "BIG_LOTTO": _B649_SIDON_BASE,
    "DAILY_539": _T539_SIDON_BASE,
    "POWER_LOTTO_zone1": _P638_SIDON_BASE,
}

# Frozen sealed-input Git blob identities (Phase 0, verified against
# `docs/research/strategy-matrix-phase5-low-overlap-geometry-mechanism-design-r1.md`
# S1 before this task's lock; recorded here for the result's own provenance
# trail, not re-derived at runtime).
_MR = "docs/research/matrix-native-results/"

INPUT_BLOBS: dict[str, str] = {
    _MR + "diversification-constructor-frontier-b649-v1-result.json": (
        "169df1649ff0b8247ef5c779e8104079ae574cf4"
    ),
    _MR + "diversification-constructor-frontier-b649-v1-report.md": (
        "60289b021f7859f0b92ccf42f38add16b9a31158"
    ),
    _MR + "greedy-min-overlap-constructor-t539-v1-result.json": (
        "346544f3a644a3083ef9863bd7f35a345a50f531"
    ),
    _MR + "greedy-min-overlap-constructor-t539-v1-report.md": (
        "c542920fc8bc900dcdb8e148cde772d22b80a731"
    ),
    _MR + "diversification-coverage-t539-v1-result.json": (
        "013f4fbc1de6d62966b4c09e6f4bca5f5ae8a032"
    ),
    _MR + "diversification-coverage-t539-v1-report.md": (
        "30e92c82033c67cabc92f2ac17131c328106d739"
    ),
    _MR + "greedy-min-overlap-constructor-p638-zone1-v1-result.json": (
        "7665d8bd84bf0c5d9a9004afb29e61ff8d421ff5"
    ),
    _MR + "greedy-min-overlap-constructor-p638-zone1-v1-report.md": (
        "958a1a71b7169df352dd6a71ec196d63df7a90aa"
    ),
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-result.json": (
        "f75ce278096d120ab368a058dba0f6262e9e8041"
    ),
    "docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-report.md": (
        "ca7754640ecd41f70351330382106e28bcd4fa53"
    ),
    "tools/generate_strategy_matrix_phase5_non_sidon_low_overlap_synthesis.py": (
        "5d0ad0728486ee0030510158e9262d1dc3ee6763"
    ),
    (
        "docs/research/matrix-native-results/"
        "strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-result.json"
    ): "d9e5d86582e71ba86f8e48d091f31eaf824bf224",
    (
        "docs/research/matrix-native-results/"
        "strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md"
    ): "2720632e56c56245a0ca18566aafda26d9d8b533",
}


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError(
            "preregistration hash mismatch -- the locked parameters file was "
            "modified after locking; refusing to execute against tampered parameters"
        )
    result: dict[str, Any] = locked
    return result


def _ticket_bitmask(ticket: Ticket) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def _validate_portfolio(portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int) -> None:
    if len(portfolio) != len(set(portfolio)):
        raise ValueError("duplicate_count invariant violated: duplicate tickets in portfolio")
    for ticket in portfolio:
        if len(ticket) != draw_size or len(set(ticket)) != draw_size:
            raise ValueError("ticket does not contain draw_size distinct numbers")
        if tuple(sorted(ticket)) != ticket:
            raise ValueError("ticket is not ascending-sorted")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError("ticket number outside 1..pool_size")


def _portfolio_sha256(portfolio: tuple[Ticket, ...]) -> str:
    encoded = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":")).encode(
        "utf-8"
    )
    return canonical_json.sha256_hex(encoded)


def multiplicity_prefix_counts(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    ladder: tuple[int, ...],
    sidon_masks: tuple[int, ...],
    armb_masks: tuple[int, ...],
) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """One streaming pass over the complete winning space for both arms at once.

    For each winner, walks tickets `0..max_k-1` in order for both arms,
    maintaining a running hit count, and records that running count into the
    matching ladder rung's `N_c` array whenever the ticket index reaches a
    ladder boundary. No winner or per-winner multiplicity is retained.
    """

    max_k = len(sidon_masks)
    ladder_flags = [False] * max_k
    for k in ladder:
        ladder_flags[k - 1] = True

    n_sidon: dict[int, list[int]] = {k: [0] * (k + 1) for k in ladder}
    n_armb: dict[int, list[int]] = {k: [0] * (k + 1) for k in ladder}

    for winner in itertools.combinations(range(1, pool_size + 1), draw_size):
        winner_mask = 0
        for number in winner:
            winner_mask |= 1 << (number - 1)
        hits_sidon = 0
        hits_armb = 0
        for idx in range(max_k):
            if (winner_mask & sidon_masks[idx]).bit_count() >= minimum_matches:
                hits_sidon += 1
            if (winner_mask & armb_masks[idx]).bit_count() >= minimum_matches:
                hits_armb += 1
            if ladder_flags[idx]:
                k = idx + 1
                n_sidon[k][hits_sidon] += 1
                n_armb[k][hits_armb] += 1

    return n_sidon, n_armb


@dataclass(frozen=True)
class MultiplicityIdentities:
    total_winning_combinations: int
    ticket_count: int
    hit_event_size_per_ticket: int
    total_hit_incidence: int
    multiplicity_counts: tuple[int, ...]
    covered: int
    redundancy: int
    collision_moments: tuple[int, ...]
    inclusion_exclusion_covered: int
    q: Fraction


def _moment_at(identities: MultiplicityIdentities, j: int) -> int:
    """S_j; 0 whenever j exceeds ticket_count (C(c,j)=0 for every c<=ticket_count<j)."""

    if j < len(identities.collision_moments):
        return identities.collision_moments[j]
    return 0


def derive_multiplicity_identities(
    n_c: list[int], pool_size: int, draw_size: int, minimum_matches: int
) -> MultiplicityIdentities:
    k = len(n_c) - 1
    total_winning_combinations = sum(n_c)
    if total_winning_combinations != math.comb(pool_size, draw_size):
        raise ArithmeticError("n_c_sums_to_winning_space identity failed")

    hit_event_size_per_ticket = qualifying_ticket_count(pool_size, draw_size, minimum_matches)
    total_hit_incidence = sum(c * count for c, count in enumerate(n_c))
    if total_hit_incidence != k * hit_event_size_per_ticket:
        raise ArithmeticError("fixed_incidence_identity failed")

    covered = sum(n_c[1:])
    redundancy = sum((c - 1) * n_c[c] for c in range(2, k + 1))
    if redundancy != total_hit_incidence - covered:
        raise ArithmeticError("redundancy_identity failed")

    collision_moments = tuple(
        sum(math.comb(c, order) * n_c[c] for c in range(k + 1)) for order in range(k + 1)
    )
    inclusion_exclusion_covered = sum(
        moment if order % 2 else -moment
        for order, moment in enumerate(collision_moments[1:], start=1)
    )
    if inclusion_exclusion_covered != covered:
        raise ArithmeticError("inclusion_exclusion_identity failed")

    q = Fraction(covered, total_winning_combinations)

    return MultiplicityIdentities(
        total_winning_combinations=total_winning_combinations,
        ticket_count=k,
        hit_event_size_per_ticket=hit_event_size_per_ticket,
        total_hit_incidence=total_hit_incidence,
        multiplicity_counts=tuple(n_c),
        covered=covered,
        redundancy=redundancy,
        collision_moments=collision_moments,
        inclusion_exclusion_covered=inclusion_exclusion_covered,
        q=q,
    )


def _parse_fraction(exact: str) -> Fraction:
    numerator, denominator = exact.split("/")
    return Fraction(int(numerator), int(denominator))


def load_sealed_q(lottery_key: str) -> tuple[dict[int, Fraction], dict[int, Fraction]]:
    """Return `(sealed_q_sidon_by_k, sealed_q_arm_b_by_k)` for one lottery, freshly read."""

    if lottery_key == "BIG_LOTTO":
        data = json.loads(
            (
                MATRIX_RESULTS / "diversification-constructor-frontier-b649-v1-result.json"
            ).read_text(encoding="utf-8")
        )
        sidon = {int(k): _parse_fraction(v["exact"]) for k, v in data["q"]["a"]["3"].items()}
        armb = {int(k): _parse_fraction(v["exact"]) for k, v in data["q"]["b"]["3"].items()}
        return sidon, armb
    if lottery_key == "DAILY_539":
        sidon_data = json.loads(
            (MATRIX_RESULTS / "diversification-coverage-t539-v1-result.json").read_text(
                encoding="utf-8"
            )
        )
        armb_data = json.loads(
            (MATRIX_RESULTS / "greedy-min-overlap-constructor-t539-v1-result.json").read_text(
                encoding="utf-8"
            )
        )
        sidon = {
            int(k): _parse_fraction(v["exact"]) for k, v in sidon_data["q_sidon"]["3"].items()
        }
        armb = {int(k): _parse_fraction(v["exact"]) for k, v in armb_data["q"]["b"]["3"].items()}
        return sidon, armb
    if lottery_key == "POWER_LOTTO_zone1":
        sidon_data = json.loads(
            (MATRIX_RESULTS / "diversification-coverage-p638-zone1-v1-result.json").read_text(
                encoding="utf-8"
            )
        )
        armb_data = json.loads(
            (MATRIX_RESULTS / "greedy-min-overlap-constructor-p638-zone1-v1-result.json").read_text(
                encoding="utf-8"
            )
        )
        sidon = {
            int(k): _parse_fraction(v["exact"]) for k, v in sidon_data["q_sidon"]["3"].items()
        }
        armb = {int(k): _parse_fraction(v["exact"]) for k, v in armb_data["q"]["b"]["3"].items()}
        return sidon, armb
    raise ValueError(f"unknown lottery_key {lottery_key!r}")


def _rational(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
    }


def _geometry_out(geometry: PortfolioGeometry) -> dict[str, Any]:
    histogram = {str(r): count for r, count in geometry.ticket_pair_intersection_histogram}
    return {
        "ticket_pair_intersection_histogram": histogram,
        "overlap_profile": dict(histogram),
        "max_pairwise_overlap": geometry.max_pairwise_overlap,
        "mean_pairwise_overlap": _rational(geometry.mean_pairwise_overlap),
        "per_number_reuse_vector": list(geometry.per_number_reuse_vector),
        "unique_number_coverage": geometry.unique_number_coverage,
        "reuse_dispersion_population_variance": _rational(
            geometry.reuse_dispersion_population_variance
        ),
        "reuse_dispersion_float": geometry.reuse_dispersion,
        "duplicate_count": geometry.duplicate_count,
    }


def build_per_k_cell(
    k: int,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    identities_sidon: MultiplicityIdentities,
    identities_armb: MultiplicityIdentities,
    geometry_sidon: PortfolioGeometry,
    geometry_armb: PortfolioGeometry,
    sealed_q_sidon: Fraction,
    sealed_q_armb: Fraction,
) -> dict[str, Any]:
    if identities_sidon.q != sealed_q_sidon:
        raise ValueError(f"q_sidon_matches_sealed failed at k={k}")
    if identities_armb.q != sealed_q_armb:
        raise ValueError(f"q_arm_b_matches_sealed failed at k={k}")

    s2_geometry_sidon = s2_from_ticket_pair_intersection_histogram(
        pool_size,
        draw_size,
        minimum_matches,
        dict(geometry_sidon.ticket_pair_intersection_histogram),
    )
    s2_geometry_armb = s2_from_ticket_pair_intersection_histogram(
        pool_size,
        draw_size,
        minimum_matches,
        dict(geometry_armb.ticket_pair_intersection_histogram),
    )
    if s2_geometry_sidon != _moment_at(identities_sidon, 2):
        raise ArithmeticError(f"s2_geometry_identity failed for SIDON at k={k}")
    if s2_geometry_armb != _moment_at(identities_armb, 2):
        raise ArithmeticError(f"s2_geometry_identity failed for ARM_B at k={k}")

    if sum(geometry_sidon.per_number_reuse_vector) != k * draw_size:
        raise ArithmeticError(f"reuse_vector_identity failed for SIDON at k={k}")
    if sum(geometry_armb.per_number_reuse_vector) != k * draw_size:
        raise ArithmeticError(f"reuse_vector_identity failed for ARM_B at k={k}")
    if geometry_sidon.duplicate_count != 0 or geometry_armb.duplicate_count != 0:
        raise ArithmeticError(f"zero_duplicates check failed at k={k}")

    if _moment_at(identities_armb, 1) != _moment_at(identities_sidon, 1):
        raise ArithmeticError(f"S1_B != S1_S at k={k}")
    if k == 1 and identities_armb.covered != identities_sidon.covered:
        raise ArithmeticError("k=1 sanity check failed: ARM_B and SIDON coverage must agree")
    if k == 1 and identities_armb.redundancy != identities_sidon.redundancy:
        raise ArithmeticError("k=1 sanity check failed: ARM_B and SIDON redundancy must agree")

    delta_covered = identities_armb.covered - identities_sidon.covered
    delta_redundancy = identities_armb.redundancy - identities_sidon.redundancy
    if delta_redundancy != -delta_covered:
        raise ArithmeticError(f"delta_redundancy != -delta_covered at k={k}")

    max_j = max(len(identities_sidon.collision_moments), len(identities_armb.collision_moments)) - 1
    delta_collision_moments = {
        j: _moment_at(identities_armb, j) - _moment_at(identities_sidon, j)
        for j in range(max_j + 1)
    }

    reconstructed_delta_covered = 0
    for j in range(2, max_j + 1):
        sign = -1 if j % 2 == 0 else 1
        reconstructed_delta_covered += sign * delta_collision_moments[j]
    if reconstructed_delta_covered != delta_covered:
        raise ArithmeticError(f"signed decomposition mismatch at k={k}")

    pairwise_component = -delta_collision_moments.get(2, 0)
    higher_order_terms = {
        j: ((-1) ** (j + 1)) * delta_collision_moments[j] for j in range(3, max_j + 1)
    }
    higher_order_residual = sum(higher_order_terms.values())
    if pairwise_component + higher_order_residual != delta_covered:
        raise ArithmeticError(f"P + H != DELTA_COVERED at k={k}")

    abs_higher_order_sum = sum(abs(term) for term in higher_order_terms.values())
    contribution_share_denominator = abs(pairwise_component) + abs_higher_order_sum

    gain_over_random_ratio_to_sidon_value: dict[str, Any] | str
    pairwise_absolute_contribution_share: dict[str, Any] | str
    mechanism_descriptor: str

    if k == 1:
        pairwise_absolute_contribution_share = "NOT_APPLICABLE_K1"
        mechanism_descriptor = "NOT_APPLICABLE_K1"
        gain_over_random_ratio_to_sidon_value = "NOT_APPLICABLE_K1"
    else:
        if contribution_share_denominator > 0:
            pairwise_absolute_contribution_share = _rational(
                Fraction(abs(pairwise_component), contribution_share_denominator)
            )
        else:
            pairwise_absolute_contribution_share = "NOT_APPLICABLE_ZERO_CHANGE"

        all_higher_order_zero = all(term == 0 for term in higher_order_terms.values())
        if pairwise_component == delta_covered and all_higher_order_zero:
            mechanism_descriptor = "PAIRWISE_COLLISION_EXACTLY_SUFFICIENT"
        elif (
            pairwise_component > 0
            and contribution_share_denominator > 0
            and Fraction(abs(pairwise_component), contribution_share_denominator) > Fraction(1, 2)
            and not all_higher_order_zero
        ):
            mechanism_descriptor = "PAIRWISE_COLLISION_PRIMARY_WITH_HIGHER_ORDER_RESIDUAL"
        else:
            mechanism_descriptor = "HIGHER_ORDER_MULTIPLICITY_PRIMARY_OR_PAIRWISE_OPPOSING"

        q_random_gt1 = exact_random_portfolio_coverage(pool_size, draw_size, minimum_matches, k)
        gain_over_random_ratio_to_sidon_value = _rational(
            gain_over_random_ratio_to_sidon(identities_armb.q, q_random_gt1, identities_sidon.q)
        )

    q_random = exact_random_portfolio_coverage(pool_size, draw_size, minimum_matches, k)
    relative_lift_vs_random_value = _rational(relative_lift_vs_random(identities_armb.q, q_random))
    relative_coverage_delta_vs_sidon_value = _rational(
        relative_coverage_delta_vs_sidon(identities_armb.q, identities_sidon.q)
    )

    def arm_out(
        identities: MultiplicityIdentities, geometry: PortfolioGeometry, s2_geometry: int
    ) -> dict[str, Any]:
        return {
            "ticket_count": identities.ticket_count,
            "hit_event_size_per_ticket": identities.hit_event_size_per_ticket,
            "total_hit_incidence": identities.total_hit_incidence,
            "multiplicity_counts": {
                str(c): count for c, count in enumerate(identities.multiplicity_counts)
            },
            "covered": identities.covered,
            "redundancy": identities.redundancy,
            "collision_moments": {
                str(j): moment for j, moment in enumerate(identities.collision_moments)
            },
            "inclusion_exclusion_covered": identities.inclusion_exclusion_covered,
            "q": _rational(identities.q),
            "geometry": _geometry_out(geometry),
            "s2_geometry": s2_geometry,
            "s2_multiplicity": _moment_at(identities, 2),
        }

    return {
        "arms": {
            "ARM_B": arm_out(identities_armb, geometry_armb, s2_geometry_armb),
            "SIDON": arm_out(identities_sidon, geometry_sidon, s2_geometry_sidon),
        },
        "comparison": {
            "delta_direction": "ARM_B_MINUS_SIDON",
            "delta_covered": delta_covered,
            "delta_redundancy": delta_redundancy,
            "delta_collision_moments": {str(j): v for j, v in delta_collision_moments.items()},
            "pairwise_component": pairwise_component,
            "higher_order_signed_terms": {str(j): v for j, v in higher_order_terms.items()},
            "higher_order_residual": higher_order_residual,
            "pairwise_absolute_contribution_share": pairwise_absolute_contribution_share,
            "mechanism_descriptor": mechanism_descriptor,
            "relative_lift_vs_random": relative_lift_vs_random_value,
            "relative_coverage_delta_vs_sidon": relative_coverage_delta_vs_sidon_value,
            "gain_over_random_ratio_to_sidon": gain_over_random_ratio_to_sidon_value,
        },
        "checks": {
            "n_c_sums_to_winning_space": True,
            "fixed_incidence_identity": True,
            "redundancy_identity": True,
            "inclusion_exclusion_identity": True,
            "s2_geometry_identity": True,
            "reuse_vector_identity": True,
            "zero_duplicates": True,
            "q_arm_b_matches_sealed": True,
            "q_sidon_matches_sealed": True,
        },
    }


def run_lottery(lottery_key: str, locked_lottery: dict[str, Any]) -> dict[str, Any]:
    pool_size: int = locked_lottery["pool_size"]
    draw_size: int = locked_lottery["draw_size"]
    sidon_fn, armb_fn = CONSTRUCTORS[lottery_key]

    if list(locked_lottery["sidon_base_set_0_indexed"]) != list(SIDON_BASE_SETS[lottery_key]):
        raise ValueError(f"{lottery_key}: Sidon base set drifted from locked parameters")

    runtime: dict[str, float] = {}

    t0 = time.perf_counter()
    sidon_20 = sidon_fn(MAX_K)
    runtime["sidon_seconds"] = time.perf_counter() - t0
    _validate_portfolio(sidon_20, pool_size, draw_size)

    t0 = time.perf_counter()
    armb_20 = armb_fn(MAX_K)
    runtime["arm_b_seconds"] = time.perf_counter() - t0
    _validate_portfolio(armb_20, pool_size, draw_size)

    portfolio_sha256 = {
        "SIDON": _portfolio_sha256(sidon_20),
        "ARM_B": _portfolio_sha256(armb_20),
    }

    sidon_masks = tuple(_ticket_bitmask(t) for t in sidon_20)
    armb_masks = tuple(_ticket_bitmask(t) for t in armb_20)

    t0 = time.perf_counter()
    n_sidon, n_armb = multiplicity_prefix_counts(
        pool_size, draw_size, MINIMUM_MATCHES, LADDER, sidon_masks, armb_masks
    )
    runtime["enumeration_seconds"] = time.perf_counter() - t0

    sealed_q_sidon, sealed_q_armb = load_sealed_q(lottery_key)

    t0 = time.perf_counter()
    per_k: dict[str, dict[str, Any]] = {}
    for k in LADDER:
        identities_sidon = derive_multiplicity_identities(
            n_sidon[k], pool_size, draw_size, MINIMUM_MATCHES
        )
        identities_armb = derive_multiplicity_identities(
            n_armb[k], pool_size, draw_size, MINIMUM_MATCHES
        )
        geometry_sidon = portfolio_geometry(sidon_20[:k], pool_size, draw_size)
        geometry_armb = portfolio_geometry(armb_20[:k], pool_size, draw_size)
        per_k[str(k)] = build_per_k_cell(
            k,
            pool_size,
            draw_size,
            MINIMUM_MATCHES,
            identities_sidon,
            identities_armb,
            geometry_sidon,
            geometry_armb,
            sealed_q_sidon[k],
            sealed_q_armb[k],
        )
    runtime["derivation_seconds"] = time.perf_counter() - t0

    return {
        "lottery_type": locked_lottery["lottery_type"],
        "zone": locked_lottery.get("zone", "NOT_APPLICABLE"),
        "pool_size": pool_size,
        "draw_size": draw_size,
        "total_winning_combinations": math.comb(pool_size, draw_size),
        "source_matrix_ids": {
            "arm_b": locked_lottery["sealed_arm_b_source_matrix_id"],
            "sidon": locked_lottery["sealed_sidon_source_matrix_id"],
        },
        "source_result_paths": {
            "arm_b": locked_lottery["sealed_arm_b_result_path"],
            "sidon": locked_lottery["sealed_sidon_result_path"],
        },
        "portfolio_sha256": portfolio_sha256,
        "per_k": per_k,
        "runtime_seconds": runtime,
    }


def run(locked: dict[str, Any]) -> dict[str, Any]:
    t_start = time.perf_counter()
    per_lottery: dict[str, dict[str, Any]] = {}
    per_lottery_runtime: dict[str, dict[str, float]] = {}
    for lottery_key in LOTTERY_KEYS:
        locked_lottery = locked["lotteries"][LOTTERY_LOCKED_KEY[lottery_key]]
        lottery_result = run_lottery(lottery_key, locked_lottery)
        per_lottery_runtime[lottery_key] = lottery_result.pop("runtime_seconds")
        per_lottery[lottery_key] = lottery_result
        print(f"{lottery_key}: done ({sum(per_lottery_runtime[lottery_key].values()):.1f}s)")

    ladder_gt1 = [k for k in LADDER if k != 1]
    redundancy_failing: list[str] = []
    pairwise_failing: list[str] = []
    descriptor_counts: dict[str, int] = {}
    all_descriptors: set[str] = set()

    for lottery_key in LOTTERY_KEYS:
        for k in LADDER:
            cell = per_lottery[lottery_key]["per_k"][str(k)]
            descriptor = cell["comparison"]["mechanism_descriptor"]
            if k != 1:
                descriptor_counts[descriptor] = descriptor_counts.get(descriptor, 0) + 1
                all_descriptors.add(descriptor)
        for k in ladder_gt1:
            cell = per_lottery[lottery_key]["per_k"][str(k)]
            redundancy_b = cell["arms"]["ARM_B"]["redundancy"]
            redundancy_s = cell["arms"]["SIDON"]["redundancy"]
            if not redundancy_b < redundancy_s:
                redundancy_failing.append(f"{lottery_key}@k={k}")
            s2_b = cell["arms"]["ARM_B"]["s2_multiplicity"]
            s2_s = cell["arms"]["SIDON"]["s2_multiplicity"]
            if not s2_b < s2_s:
                pairwise_failing.append(f"{lottery_key}@k={k}")

    redundancy_reduction_value = (
        "REDUNDANCY_REDUCTION_REPLICATED"
        if not redundancy_failing
        else "REDUNDANCY_REDUCTION_NOT_UNIVERSAL"
    )
    pairwise_collision_value = (
        "PAIRWISE_COLLISION_REDUCTION_REPLICATED"
        if not pairwise_failing
        else "PAIRWISE_COLLISION_NOT_UNIVERSALLY_EXPLANATORY"
    )
    aggregate_mechanism_descriptor = (
        next(iter(all_descriptors)) if len(all_descriptors) == 1 else "MIXED_BY_LOTTERY_OR_K"
    )
    final_classification = (
        f"{redundancy_reduction_value}__{pairwise_collision_value}"
        f"__AGGREGATE_DESCRIPTOR_{aggregate_mechanism_descriptor}"
    )

    total_runtime = time.perf_counter() - t_start
    peak_memory_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return {
        "study_id": locked["study_id"],
        "source_type": "STRATEGY_MATRIX_NATIVE_MECHANISM",
        "evidence_type": "EXACT_COMBINATORIAL",
        "canonical_input": {
            "repository": "kelvinhuang0327/MathStatisticalAnalysis",
            "commit": locked["canonical_input_commit"],
            "tree": locked["canonical_input_tree"],
            "locked_preregistration_path": str(
                MATRIX_RESULTS / "low-overlap-geometry-mechanism-v1-preregistration.md"
            ),
            "locked_preregistration_sha256": canonical_json.sha256_hex(
                canonical_json.canonical_bytes(locked)
            ),
            "input_blobs": dict(INPUT_BLOBS),
        },
        "scope": {
            "historical_draws_read": False,
            "monte_carlo": False,
            "p638_zone2": "NOT_RUN",
            "arm_c": "NOT_RUN",
            "secondary_events": "NOT_RUN",
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
        },
        "metric_semantics": {
            "RELATIVE_LIFT_VS_RANDOM": "(Q_B-Q_R)/Q_R",
            "RELATIVE_COVERAGE_DELTA_VS_SIDON": "(Q_B-Q_S)/Q_S",
            "GAIN_OVER_RANDOM_RATIO_TO_SIDON": "(Q_B-Q_R)/(Q_S-Q_R)",
            "sealed_REL_GAIN_OVER_SIDON_maps_to": "GAIN_OVER_RANDOM_RATIO_TO_SIDON",
        },
        "ladder": list(LADDER),
        "minimum_matches": MINIMUM_MATCHES,
        "per_lottery": per_lottery,
        "classifications": {
            "redundancy_reduction": {
                "value": redundancy_reduction_value,
                "failing_or_equal_cells": redundancy_failing,
            },
            "pairwise_collision_reduction": {
                "value": pairwise_collision_value,
                "failing_or_equal_cells": pairwise_failing,
            },
            "mechanism_descriptor_counts": descriptor_counts,
            "aggregate_mechanism_descriptor": aggregate_mechanism_descriptor,
            "global_optimum_status": "UNKNOWN",
        },
        "runtime_seconds": {
            "portfolio_generation_by_lottery_and_arm": {
                lottery_key: {
                    "SIDON": per_lottery_runtime[lottery_key]["sidon_seconds"],
                    "ARM_B": per_lottery_runtime[lottery_key]["arm_b_seconds"],
                }
                for lottery_key in LOTTERY_KEYS
            },
            "winning_space_enumeration_by_lottery": {
                lottery_key: per_lottery_runtime[lottery_key]["enumeration_seconds"]
                for lottery_key in LOTTERY_KEYS
            },
            "derivation_and_validation": sum(
                per_lottery_runtime[lottery_key]["derivation_seconds"]
                for lottery_key in LOTTERY_KEYS
            ),
            "total": total_runtime,
        },
        "peak_memory_bytes": peak_memory_bytes,
        "final_classification": final_classification,
    }


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    classifications = result["classifications"]
    print(f"redundancy_reduction: {classifications['redundancy_reduction']['value']}")
    pairwise_status = classifications["pairwise_collision_reduction"]["value"]
    print(f"pairwise_collision_reduction: {pairwise_status}")
    print(f"aggregate_mechanism_descriptor: {classifications['aggregate_mechanism_descriptor']}")
    print(f"final_classification: {result['final_classification']}")
    print(f"total runtime: {result['runtime_seconds']['total']:.1f}s")
    print(f"peak memory: {result['peak_memory_bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
