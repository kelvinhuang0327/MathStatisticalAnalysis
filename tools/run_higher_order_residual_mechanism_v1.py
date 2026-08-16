"""Execute the locked STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1 study.

Reads locked parameters from
`docs/research/matrix-native-results/higher-order-residual-mechanism-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (same
fail-closed pattern `run_low_overlap_geometry_mechanism_v1.py` uses). For
each of B649, T539, and P638 Zone-1: builds the canonical Sidon and Arm-B
`k=20` portfolios once (all smaller ladder rungs are exact prefixes, never
rebuilt independently), verifies each portfolio's SHA-256 against the
already-sealed `low-overlap-geometry-mechanism-v1-result.json`, then -- for
every `k in {3,5,10,15,20}` -- computes the exact ticket-triple intersection
histogram and derives `S3_GEOMETRY` from it, asserting exact equality
against the sealed `S3_MULTIPLICITY` (`collision_moments["3"]`) reused
read-only from that same sealed file. `T3`/`T4`/`T5`/`H`/`mechanism_
descriptor`/`DELTA_COVERED` are copied read-only from the sealed result for
side-by-side reporting, never recomputed. No winning-space enumeration is
performed anywhere in this module: that is the one thing this study reuses
from Phase 5 instead of recomputing. `MONTE_CARLO: NONE`.
`HISTORICAL_DRAWS: NOT_USED`. `P638_ZONE2`/`ARM_C`/`J4_GEOMETRY`: not
touched by any import in this module.
"""

from __future__ import annotations

import json
import math
import resource
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research.cyclic_sidon_shift import SIDON_BASE_SET_0_INDEXED as _B649_SIDON_BASE
from lottolab.research.cyclic_sidon_shift import sidon_shift_portfolio as _b649_sidon_portfolio
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
from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio
from lottolab.research.greedy_min_overlap_constructor_p638_zone1 import (
    greedy_min_overlap_portfolio_p638_zone1,
)
from lottolab.research.greedy_min_overlap_constructor_t539 import (
    greedy_min_overlap_portfolio_t539,
)
from lottolab.research.higher_order_residual_mechanism import (
    TripleShape,
    s3_from_ticket_triple_intersection_histogram,
    ticket_triple_intersection_histogram,
    triple_collision_is_impossible,
    triple_collision_mass_bound,
)

Ticket = tuple[int, ...]

_MATRIX_RESULTS = "docs/research/matrix-native-results/"
MATRIX_RESULTS = Path(_MATRIX_RESULTS)
PREREGISTRATION_HASH_PATH = (
    MATRIX_RESULTS / "higher-order-residual-mechanism-v1-preregistration-hash.json"
)
SEALED_PHASE5_RESULT_PATH = MATRIX_RESULTS / "low-overlap-geometry-mechanism-v1-result.json"
SEALED_PHASE5_PREREGISTRATION_HASH_PATH = (
    MATRIX_RESULTS / "low-overlap-geometry-mechanism-v1-preregistration-hash.json"
)
OUTPUT_PATH = MATRIX_RESULTS / "higher-order-residual-mechanism-v1-result.json"

LADDER: tuple[int, ...] = (1, 3, 5, 10, 15, 20)
TRIPLE_LADDER: tuple[int, ...] = (3, 5, 10, 15, 20)
MAX_K = 20
MINIMUM_MATCHES = 3
LOTTERY_KEYS: tuple[str, ...] = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO_zone1")
LOTTERY_LOCKED_KEY: dict[str, str] = {
    "BIG_LOTTO": "big_lotto",
    "DAILY_539": "daily_539",
    "POWER_LOTTO_zone1": "power_lotto_zone1",
}
ARM_KEYS: tuple[str, ...] = ("ARM_B", "SIDON")

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

# Frozen sealed-input Git blob identities (recorded at lock time in
# `higher-order-residual-mechanism-v1-preregistration-hash.json`; repeated
# here only for this result's own provenance trail, not re-derived at
# runtime -- matches `run_low_overlap_geometry_mechanism_v1.py`'s
# `INPUT_BLOBS` convention).
INPUT_BLOBS: dict[str, str] = {
    _MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-result.json": (
        "dc17f0b39c9baf81f8c85162d5db554e7ca2797a"
    ),
    _MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-report.md": (
        "0243589b14068ea6a3f32d8af37e4db9b7569065"
    ),
    _MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-preregistration.md": (
        "17b1ae14523bcd63f48d226a3134a2c5531ee654"
    ),
    _MATRIX_RESULTS + "low-overlap-geometry-mechanism-v1-preregistration-hash.json": (
        "c26e61a62dbebcfa44881d5a23f044a0ed52e04f"
    ),
    "src/lottolab/research/low_overlap_geometry_mechanism.py": (
        "20b6e0d70b17ef4e34c4d3d6f89196685c5bd22c"
    ),
    "src/lottolab/research/higher_order_residual_mechanism.py": (
        "2bc6eb7857ba373b723ac9e4d6c4dc89080e464c"
    ),
    "src/lottolab/research/cyclic_sidon_shift.py": "d07efb5c71a0b25bb00ba3823e208c57aabb306e",
    "src/lottolab/research/cyclic_sidon_shift_t539.py": (
        "f6b95bed2e0d51ed81781efd096d4f87d88606a1"
    ),
    "src/lottolab/research/cyclic_sidon_shift_p638.py": (
        "736d0c7e8efc79f68e989921be3e5e0742617e97"
    ),
    "src/lottolab/research/greedy_min_overlap_constructor.py": (
        "5511f67d981f7f8a1c33183c966d76ee50249d7d"
    ),
    "src/lottolab/research/greedy_min_overlap_constructor_t539.py": (
        "372542aa0c164d3548a6aaa91dd56b28821d0eaa"
    ),
    "src/lottolab/research/greedy_min_overlap_constructor_p638_zone1.py": (
        "622898a9f0a9f4c72af456a21af83c0fc63c7d45"
    ),
}


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError(
            "STOP_PHASE6_SEALED_INPUT_DRIFT: preregistration hash mismatch -- the "
            "locked parameters file was modified after locking; refusing to execute "
            "against tampered parameters"
        )
    result: dict[str, Any] = locked
    return result


def load_sealed_phase5_result(locked: dict[str, Any]) -> dict[str, Any]:
    sealed_meta = locked["sealed_phase5"]
    prereg_hash_record = json.loads(
        SEALED_PHASE5_PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8")
    )
    sealed_hash = sealed_meta["preregistration_hash_sha256"]
    if prereg_hash_record["preregistration_hash_sha256"] != sealed_hash:
        raise ValueError(
            "STOP_PHASE6_SEALED_INPUT_DRIFT: sealed Phase-5 preregistration hash "
            "drifted from the value frozen in this study's own lock"
        )
    result: dict[str, Any] = json.loads(SEALED_PHASE5_RESULT_PATH.read_text(encoding="utf-8"))
    if result["study_id"] != sealed_meta["study_id"]:
        raise ValueError("STOP_PHASE6_SEALED_INPUT_DRIFT: sealed Phase-5 study_id mismatch")
    return result


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


def _rational(value: Fraction) -> dict[str, Any]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "exact": f"{value.numerator}/{value.denominator}",
    }


def _shape_key(shape: TripleShape) -> str:
    return f"{shape[0]},{shape[1]},{shape[2]},{shape[3]}"


def compute_triple_cell(
    prefix: tuple[Ticket, ...],
    pool_size: int,
    draw_size: int,
    k: int,
    sealed_arm_k: dict[str, Any],
) -> dict[str, Any]:
    """Derive one (lottery, arm, k) triple-geometry cell from a portfolio prefix.

    Raises on any invariant violation -- an unrealizable (negative-region)
    shape, a histogram whose total triple count does not equal ``C(k,3)``,
    or ``S3_GEOMETRY != S3_MULTIPLICITY`` -- so a written result implies
    every one of these checks already passed (Phase 5's "no partial result
    is ever persisted" convention).
    """

    histogram: dict[TripleShape, int] = dict(ticket_triple_intersection_histogram(prefix))
    total_triples = sum(histogram.values())
    expected_triples = math.comb(k, 3)
    if total_triples != expected_triples:
        raise ArithmeticError(
            f"triple_histogram_total_identity failed: {total_triples} != "
            f"C({k},3)={expected_triples}"
        )

    s3_geometry = s3_from_ticket_triple_intersection_histogram(
        pool_size, draw_size, MINIMUM_MATCHES, histogram
    )
    s3_multiplicity = int(sealed_arm_k["collision_moments"]["3"])
    s3_geometry_identity = s3_geometry == s3_multiplicity
    if not s3_geometry_identity:
        raise ArithmeticError(
            f"STOP_PHASE6_S3_GEOMETRY_IDENTITY_FAILED: k={k}: "
            f"s3_geometry={s3_geometry} != s3_multiplicity={s3_multiplicity}"
        )

    required_mass = 3 * MINIMUM_MATCHES - draw_size
    saturated_triple_count = sum(
        count
        for shape, count in histogram.items()
        if triple_collision_mass_bound(shape[0], shape[1], shape[2], shape[3]) == required_mass
    )
    all_impossible = all(
        triple_collision_is_impossible(
            draw_size, MINIMUM_MATCHES, shape[0], shape[1], shape[2], shape[3]
        )
        for shape in histogram
    )
    mass_bound_prediction_correct = all_impossible == (s3_multiplicity == 0)

    return {
        "ticket_triple_intersection_histogram": {
            _shape_key(shape): count for shape, count in sorted(histogram.items())
        },
        "s3_geometry": s3_geometry,
        "s3_multiplicity": s3_multiplicity,
        "s3_geometry_identity": s3_geometry_identity,
        "saturated_triple_count": saturated_triple_count,
        "mass_bound_prediction_correct": mass_bound_prediction_correct,
        "sealed_max_pairwise_overlap": sealed_arm_k["geometry"]["max_pairwise_overlap"],
    }


def run_lottery(
    lottery_key: str, locked_lottery: dict[str, Any], sealed_result: dict[str, Any]
) -> dict[str, Any]:
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

    portfolios: dict[str, tuple[Ticket, ...]] = {"SIDON": sidon_20, "ARM_B": armb_20}
    portfolio_sha256 = {arm: _portfolio_sha256(portfolio) for arm, portfolio in portfolios.items()}

    sealed_lottery = sealed_result["per_lottery"][lottery_key]
    sealed_portfolio_sha256 = sealed_lottery["portfolio_sha256"]
    portfolio_hash_status: dict[str, bool] = {}
    for arm in ARM_KEYS:
        matches = portfolio_sha256[arm] == sealed_portfolio_sha256[arm]
        portfolio_hash_status[arm] = matches
        if not matches:
            raise ValueError(
                f"STOP_PHASE6_PORTFOLIO_HASH_MISMATCH: {lottery_key}/{arm} "
                f"regenerated={portfolio_sha256[arm]} sealed={sealed_portfolio_sha256[arm]}"
            )

    t0 = time.perf_counter()
    per_k: dict[str, Any] = {}
    for k in TRIPLE_LADDER:
        arms_out: dict[str, Any] = {}
        for arm in ARM_KEYS:
            prefix = portfolios[arm][:k]
            sealed_arm_k = sealed_lottery["per_k"][str(k)]["arms"][arm]
            arms_out[arm] = compute_triple_cell(prefix, pool_size, draw_size, k, sealed_arm_k)

        sealed_comparison = sealed_lottery["per_k"][str(k)]["comparison"]
        sealed_terms = sealed_comparison["higher_order_signed_terms"]
        delta_covered = int(sealed_comparison["delta_covered"])
        higher_order_residual = int(sealed_comparison["higher_order_residual"])
        residual_ratio: dict[str, Any] | str
        if delta_covered != 0:
            residual_ratio = _rational(Fraction(higher_order_residual, delta_covered))
        else:
            residual_ratio = "NOT_APPLICABLE_ZERO_NET_GAIN"

        per_k[str(k)] = {
            "arms": arms_out,
            "comparison": {
                "sealed_t3": int(sealed_terms.get("3", 0)),
                "sealed_t4": int(sealed_terms.get("4", 0)),
                "sealed_t5": int(sealed_terms.get("5", 0)),
                "sealed_higher_order_residual": higher_order_residual,
                "sealed_mechanism_descriptor": sealed_comparison["mechanism_descriptor"],
                "sealed_delta_covered": delta_covered,
                "residual_to_net_gain_ratio": residual_ratio,
            },
            "checks": {
                "portfolio_sha256_matches_sealed": True,
                "triple_region_sizes_all_nonnegative": True,
                "s3_geometry_identity": (
                    arms_out["ARM_B"]["s3_geometry_identity"]
                    and arms_out["SIDON"]["s3_geometry_identity"]
                ),
            },
        }
    runtime["triple_geometry_seconds"] = time.perf_counter() - t0

    return {
        "lottery_type": locked_lottery["lottery_type"],
        "zone": locked_lottery.get("zone", "NOT_APPLICABLE"),
        "pool_size": pool_size,
        "draw_size": draw_size,
        "portfolio_sha256": portfolio_sha256,
        "portfolio_hash_status": portfolio_hash_status,
        "per_k": per_k,
        "runtime_seconds": runtime,
    }


def run(locked: dict[str, Any], sealed_result: dict[str, Any]) -> dict[str, Any]:
    t_start = time.perf_counter()
    per_lottery: dict[str, dict[str, Any]] = {}
    per_lottery_runtime: dict[str, dict[str, float]] = {}
    for lottery_key in LOTTERY_KEYS:
        locked_lottery = locked["lotteries"][LOTTERY_LOCKED_KEY[lottery_key]]
        lottery_result = run_lottery(lottery_key, locked_lottery, sealed_result)
        per_lottery_runtime[lottery_key] = lottery_result.pop("runtime_seconds")
        per_lottery[lottery_key] = lottery_result
        print(f"{lottery_key}: done ({sum(per_lottery_runtime[lottery_key].values()):.1f}s)")

    failing_identity_cells: list[str] = []
    exception_cells: list[str] = []
    saturated_triple_count_by_k: dict[str, dict[str, dict[str, int]]] = {}
    for lottery_key in LOTTERY_KEYS:
        saturated_triple_count_by_k[lottery_key] = {arm: {} for arm in ARM_KEYS}
        for k in TRIPLE_LADDER:
            cell = per_lottery[lottery_key]["per_k"][str(k)]
            for arm in ARM_KEYS:
                arm_cell = cell["arms"][arm]
                saturated_triple_count_by_k[lottery_key][arm][str(k)] = arm_cell[
                    "saturated_triple_count"
                ]
                if not arm_cell["s3_geometry_identity"]:
                    failing_identity_cells.append(f"{lottery_key}/{arm}@k={k}")
                if not arm_cell["mass_bound_prediction_correct"]:
                    exception_cells.append(f"{lottery_key}/{arm}@k={k}")

    s3_geometry_identity_value = (
        "S3_GEOMETRY_IDENTITY_REPLICATED"
        if not failing_identity_cells
        else "S3_GEOMETRY_IDENTITY_FAILED"
    )
    mass_bound_value = (
        "MASS_BOUND_PREDICTS_ZERO_SPLIT"
        if not exception_cells
        else "MASS_BOUND_PREDICTION_NOT_UNIVERSAL"
    )
    final_classification = f"{s3_geometry_identity_value}__{mass_bound_value}"

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
                MATRIX_RESULTS / "higher-order-residual-mechanism-v1-preregistration.md"
            ),
            "locked_preregistration_sha256": canonical_json.sha256_hex(
                canonical_json.canonical_bytes(locked)
            ),
            "sealed_phase5_result_path": str(SEALED_PHASE5_RESULT_PATH),
            "sealed_phase5_result_blob": locked["sealed_phase5"]["result_blob_sha1"],
            "sealed_phase5_preregistration_sha256": locked["sealed_phase5"][
                "preregistration_hash_sha256"
            ],
            "input_blobs": dict(INPUT_BLOBS),
        },
        "scope": {
            "historical_draws_read": False,
            "monte_carlo": False,
            "native_winning_space_enumeration": False,
            "p638_zone2": "NOT_RUN",
            "arm_c": "NOT_RUN",
            "secondary_events": "NOT_RUN",
            "j4_geometry": "NOT_RUN",
            "predictive_advantage": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
        },
        "ladder": list(LADDER),
        "triple_ladder": list(TRIPLE_LADDER),
        "minimum_matches": MINIMUM_MATCHES,
        "per_lottery": per_lottery,
        "classifications": {
            "s3_geometry_identity": {
                "value": s3_geometry_identity_value,
                "failing_cells": failing_identity_cells,
            },
            "mass_bound_prediction": {
                "value": mass_bound_value,
                "exception_cells": exception_cells,
            },
            "saturated_triple_count_by_k": saturated_triple_count_by_k,
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
            "triple_geometry_computation_by_lottery": {
                lottery_key: per_lottery_runtime[lottery_key]["triple_geometry_seconds"]
                for lottery_key in LOTTERY_KEYS
            },
            "derivation_and_validation": 0.0,
            "total": total_runtime,
        },
        "peak_memory_bytes": peak_memory_bytes,
        "final_classification": final_classification,
    }


def main() -> None:
    locked = load_locked_parameters()
    sealed_result = load_sealed_phase5_result(locked)
    result = run(locked, sealed_result)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    OUTPUT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    classifications = result["classifications"]
    print(f"s3_geometry_identity: {classifications['s3_geometry_identity']['value']}")
    print(f"mass_bound_prediction: {classifications['mass_bound_prediction']['value']}")
    print(f"final_classification: {result['final_classification']}")
    print(f"total runtime: {result['runtime_seconds']['total']:.1f}s")
    print(f"peak memory: {result['peak_memory_bytes'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
