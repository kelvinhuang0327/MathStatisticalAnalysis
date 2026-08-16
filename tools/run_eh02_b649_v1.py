"""Execute the locked EH02_CROSS_LOTTERY_TRANSFER_ENTROPY_B649_V1 experiment.

Reads locked parameters from
`docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (same
fail-closed pattern `run_eh01_eh10_b649_v1.py` uses). Runs the required
synthetic-fixture check FIRST and stops (`STOP_SYNTHETIC_FIXTURE_FAIL`) if it
does not reproduce the two hand-derived exact values -- no B649/T539/P638
value is read before that check passes. Then loads the three pinned
datasets read-only and refuses to run if any dataset's identity does not
exactly match the locked identity (`STOP_DATASET_AUTHORITY_MISMATCH`).

Each of `EDGE_1 (T539->B649)` and `EDGE_2 (P638Z1->B649)` gets: primary
`GLOBAL` transfer entropy + `MI` comparator, `ERA4` robustness, a
28-day-stale timing-control point estimate, a reverse-direction
directionality control, and a `B=2` alternate-binning diagnostic -- exactly
Sec. 3-9 of the locked design, no more, no less. No pooled/combined
edge effect is computed at any point.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research import b649_eh01_eh10_shared as shared
from lottolab.research import b649_eh02_dataset as dataset
from lottolab.research import b649_eh02_transfer_entropy as te

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "eh02-b649-cross-lottery-transfer-entropy-v1-preregistration-hash.json"
)
RESULT_PATH = Path(
    "docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-result.json"
)

FIXTURE_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# Preregistration hash re-verification
# ---------------------------------------------------------------------------


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise te.Eh02DesignError(
            "STOP_SPEC_AUTHORITY_MISMATCH: preregistration hash mismatch -- the locked "
            "parameters file was modified after locking; refusing to execute"
        )
    return locked


# ---------------------------------------------------------------------------
# Synthetic fixture check (MUST pass before any real data is read)
# ---------------------------------------------------------------------------


def run_synthetic_fixture_check() -> dict[str, float]:
    """Two hand-derived 3-symbol cases over the same 9 (x_prev, y_prior) pairs.

    Fixture A (full dependency, x_next = y_prior): TE = MI = ln(3) exactly.
    Fixture B (null, x_next = x_prev, y irrelevant): TE = MI = 0 exactly.
    """

    import math

    pairs = [(a, b) for a in range(3) for b in range(3)]
    x_prev = tuple(a for a, _ in pairs)
    y_prior = tuple(b for _, b in pairs)
    x_next_a = tuple(b for _, b in pairs)
    x_next_b = tuple(a for a, _ in pairs)

    te_a = te.discrete_transfer_entropy(x_next_a, x_prev, y_prior)
    mi_a = te.lagged_mutual_information(x_next_a, y_prior)
    te_b = te.discrete_transfer_entropy(x_next_b, x_prev, y_prior)
    mi_b = te.lagged_mutual_information(x_next_b, y_prior)

    expected_ln3 = math.log(3)
    checks = {
        "fixture_a_te": (te_a, expected_ln3),
        "fixture_a_mi": (mi_a, expected_ln3),
        "fixture_b_te": (te_b, 0.0),
        "fixture_b_mi": (mi_b, 0.0),
    }
    failures = [
        f"{name}: got {observed}, expected {expected}"
        for name, (observed, expected) in checks.items()
        if abs(observed - expected) > FIXTURE_TOLERANCE
    ]
    if failures:
        raise te.Eh02DesignError(
            "STOP_SYNTHETIC_FIXTURE_FAIL: " + "; ".join(failures)
        )
    return {name: observed for name, (observed, _expected) in checks.items()}


# ---------------------------------------------------------------------------
# Dataset identity verification
# ---------------------------------------------------------------------------


def verify_dataset_identity(locked: dict[str, Any], b649: Any, t539: Any, p638z1: Any) -> None:
    mismatches: list[str] = []

    def _check(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            mismatches.append(f"{label}: {actual!r} != {expected!r}")

    _check("dataset_a_row_count", b649.row_count, locked["dataset_a_row_count"])
    _check("dataset_a_date_start", b649.draw_dates[0], locked["dataset_a_date_range_start"])
    _check("dataset_a_date_end", b649.draw_dates[-1], locked["dataset_a_date_range_end"])
    _check("dataset_a_logical_sha256", b649.logical_sha256, locked["dataset_a_logical_sha256"])

    _check("dataset_b_row_count", t539.row_count, locked["dataset_b_row_count"])
    _check("dataset_b_date_start", t539.draw_dates[0], locked["dataset_b_date_range_start"])
    _check("dataset_b_date_end", t539.draw_dates[-1], locked["dataset_b_date_range_end"])
    _check("dataset_b_logical_sha256", t539.logical_sha256, locked["dataset_b_logical_sha256"])

    _check("dataset_c_row_count", p638z1.row_count, locked["dataset_c_row_count"])
    _check("dataset_c_date_start", p638z1.draw_dates[0], locked["dataset_c_date_range_start"])
    _check("dataset_c_date_end", p638z1.draw_dates[-1], locked["dataset_c_date_range_end"])
    _check("dataset_c_logical_sha256", p638z1.logical_sha256, locked["dataset_c_logical_sha256"])

    if mismatches:
        raise te.Eh02DesignError("STOP_DATASET_AUTHORITY_MISMATCH: " + "; ".join(mismatches))


# ---------------------------------------------------------------------------
# Per-edge computation
# ---------------------------------------------------------------------------


def _global_raw_p(
    edge_id: str,
    n: int,
    x_next: tuple[int, ...],
    x_prev: tuple[int, ...],
    y_prior: tuple[int, ...],
) -> tuple[float, float, tuple[tuple[int, ...], ...]]:
    observed = te.discrete_transfer_entropy(x_next, x_prev, y_prior)
    orders = tuple(
        te.global_surrogate_order(edge_id, b, n) for b in range(te.PERMUTATIONS_PER_POLICY)
    )
    te.assert_distinct_permutations(orders, edge_id=edge_id, policy=shared.GLOBAL_POLICY)
    surrogates = tuple(
        te.discrete_transfer_entropy(x_next, x_prev, te.apply_order(y_prior, order))
        for order in orders
    )
    raw_p = shared.raw_p_value(observed, surrogates)
    return observed, raw_p, orders


def _era4_raw_p(
    edge_id: str,
    n: int,
    x_next: tuple[int, ...],
    x_prev: tuple[int, ...],
    y_prior: tuple[int, ...],
) -> tuple[float, tuple[tuple[int, ...], ...]]:
    observed = te.discrete_transfer_entropy(x_next, x_prev, y_prior)
    orders = tuple(
        te.era4_surrogate_order(edge_id, b, n) for b in range(te.PERMUTATIONS_PER_POLICY)
    )
    te.assert_distinct_permutations(orders, edge_id=edge_id, policy=shared.ERA4_POLICY)
    surrogates = tuple(
        te.discrete_transfer_entropy(x_next, x_prev, te.apply_order(y_prior, order))
        for order in orders
    )
    raw_p = shared.raw_p_value(observed, surrogates)
    return raw_p, orders


def compute_edge(
    *,
    forward_edge_id: str,
    reverse_edge_id: str,
    target_dates: tuple[str, ...],
    target_draw_ids: tuple[int, ...],
    target_bins_b3: tuple[int, ...],
    target_bins_b2: tuple[int, ...],
    source_dates: tuple[str, ...],
    source_draw_ids: tuple[int, ...],
    source_bins_b3: tuple[int, ...],
    source_bins_b2: tuple[int, ...],
    expected_eligible: int,
    expected_era4_sizes: list[int],
) -> dict[str, Any]:
    qualifying = te.build_qualifying_set(target_dates, source_dates)
    qualifying_count = len(qualifying.target_indices)
    if qualifying_count <= te.BURN_IN_OBSERVATIONS:
        raise te.Eh02DesignError(
            f"STOP_EH02_GEOMETRY_INSUFFICIENT: {forward_edge_id} qualifying count "
            f"{qualifying_count} does not clear the burn-in"
        )

    eligible_target_idx = qualifying.target_indices[te.BURN_IN_OBSERVATIONS :]
    eligible_source_idx = qualifying.source_indices[te.BURN_IN_OBSERVATIONS :]
    n_eligible = len(eligible_target_idx)

    if n_eligible != expected_eligible:
        raise te.Eh02DesignError(
            f"STOP_DATASET_AUTHORITY_MISMATCH: {forward_edge_id} eligible count "
            f"{n_eligible} != expected {expected_eligible}"
        )
    if n_eligible < te.GEOMETRY_FLOOR_TOTAL:
        raise te.Eh02DesignError(
            f"STOP_EH02_GEOMETRY_INSUFFICIENT: {forward_edge_id} eligible total "
            f"{n_eligible} < {te.GEOMETRY_FLOOR_TOTAL}"
        )
    era_sizes = [shared.era4_assignment(n_eligible).count(e) for e in (1, 2, 3, 4)]
    if era_sizes != expected_era4_sizes:
        raise te.Eh02DesignError(
            f"STOP_DATASET_AUTHORITY_MISMATCH: {forward_edge_id} ERA4 sizes {era_sizes} "
            f"!= expected {expected_era4_sizes}"
        )
    if min(era_sizes) < te.GEOMETRY_FLOOR_PER_ERA:
        raise te.Eh02DesignError(
            f"STOP_EH02_GEOMETRY_INSUFFICIENT: {forward_edge_id} min era size "
            f"{min(era_sizes)} < {te.GEOMETRY_FLOOR_PER_ERA}"
        )

    # ---- forward primary (B=3): x' = target[t], x = target[t-1], y = source[prior] ----
    x_next = tuple(target_bins_b3[t] for t in eligible_target_idx)
    x_prev = tuple(target_bins_b3[t - 1] for t in eligible_target_idx)
    y_prior = tuple(source_bins_b3[s] for s in eligible_source_idx)

    te_global, raw_p_global, global_orders = _global_raw_p(
        forward_edge_id, n_eligible, x_next, x_prev, y_prior
    )
    raw_p_era4, era4_orders = _era4_raw_p(forward_edge_id, n_eligible, x_next, x_prev, y_prior)
    mi_observed = te.lagged_mutual_information(x_next, y_prior)

    global_ledger_digest = te.permutation_ledger_digest(
        global_orders, edge_id=forward_edge_id, policy=shared.GLOBAL_POLICY
    )
    era4_ledger_digest = te.permutation_ledger_digest(
        era4_orders, edge_id=forward_edge_id, policy=shared.ERA4_POLICY
    )

    # ---- B=2 alternate-binning diagnostic (forward, GLOBAL only; reuses the
    # SAME permutation index-order sequence as the B=3 primary GLOBAL test --
    # perm_key's salt has no bin-count dimension, so this is the literal
    # formula, not a shortcut) ----
    x_next_b2 = tuple(target_bins_b2[t] for t in eligible_target_idx)
    x_prev_b2 = tuple(target_bins_b2[t - 1] for t in eligible_target_idx)
    y_prior_b2 = tuple(source_bins_b2[s] for s in eligible_source_idx)
    te_b2_observed = te.discrete_transfer_entropy(x_next_b2, x_prev_b2, y_prior_b2)
    b2_surrogates = tuple(
        te.discrete_transfer_entropy(x_next_b2, x_prev_b2, te.apply_order(y_prior_b2, order))
        for order in global_orders
    )
    raw_p_b2 = shared.raw_p_value(te_b2_observed, b2_surrogates)

    # ---- timing control: point estimate only, no permutation (Sec. 6.2) ----
    stale_source_idx = te.stale_source_indices(
        target_dates, source_dates, eligible_target_idx, stale_days=te.STALE_DAYS
    )
    stale_rows = [
        (t, s) for t, s in zip(eligible_target_idx, stale_source_idx, strict=True) if s is not None
    ]
    stale_x_next = tuple(target_bins_b3[t] for t, _ in stale_rows)
    stale_x_prev = tuple(target_bins_b3[t - 1] for t, _ in stale_rows)
    stale_y = tuple(source_bins_b3[s] for _, s in stale_rows)
    te_stale = te.discrete_transfer_entropy(stale_x_next, stale_x_prev, stale_y)
    timing_control_pass = te_global > te_stale

    # ---- reverse direction / directionality control (Sec. 7) ----
    reverse_qualifying = te.build_qualifying_set(source_dates, target_dates)
    reverse_qualifying_count = len(reverse_qualifying.target_indices)
    if reverse_qualifying_count <= te.BURN_IN_OBSERVATIONS:
        raise te.Eh02DesignError(
            f"STOP_EH02_GEOMETRY_INSUFFICIENT: {reverse_edge_id} qualifying count "
            f"{reverse_qualifying_count} does not clear the burn-in"
        )
    rev_eligible_target_idx = reverse_qualifying.target_indices[te.BURN_IN_OBSERVATIONS :]
    rev_eligible_source_idx = reverse_qualifying.source_indices[te.BURN_IN_OBSERVATIONS :]
    n_reverse = len(rev_eligible_target_idx)

    rev_x_next = tuple(source_bins_b3[t] for t in rev_eligible_target_idx)
    rev_x_prev = tuple(source_bins_b3[t - 1] for t in rev_eligible_target_idx)
    rev_y_prior = tuple(target_bins_b3[s] for s in rev_eligible_source_idx)

    te_reverse, raw_p_reverse, reverse_orders = _global_raw_p(
        reverse_edge_id, n_reverse, rev_x_next, rev_x_prev, rev_y_prior
    )
    reverse_ledger_digest = te.permutation_ledger_digest(
        reverse_orders, edge_id=reverse_edge_id, policy=shared.GLOBAL_POLICY
    )
    directionality_control_pass = raw_p_global < raw_p_reverse and raw_p_reverse > 0.10

    return {
        "edge_id": forward_edge_id,
        "reverse_edge_id": reverse_edge_id,
        "eligibility": {
            "qualifying_count": qualifying_count,
            "same_day_excluded_count": qualifying.same_day_excluded_count,
            "no_prior_count": qualifying.no_prior_count,
            "eligible_post_burn_in": n_eligible,
            "era4_partition_sizes": era_sizes,
            "reverse_qualifying_count": reverse_qualifying_count,
            "reverse_eligible_post_burn_in": n_reverse,
            "stale_eligible_count": len(stale_rows),
        },
        "primary": {
            "te_global_observed": te_global,
            "global_raw_p": raw_p_global,
            "era4_raw_p": raw_p_era4,
            "mi_comparator_observed": mi_observed,
        },
        "diagnostics": {
            "b2_te_observed": te_b2_observed,
            "b2_raw_p": raw_p_b2,
        },
        "timing_control": {
            "stale_days": te.STALE_DAYS,
            "te_observed": te_global,
            "te_stale": te_stale,
            "pass": timing_control_pass,
        },
        "directionality_control": {
            "te_reverse_observed": te_reverse,
            "forward_raw_p": raw_p_global,
            "reverse_raw_p": raw_p_reverse,
            "pass": directionality_control_pass,
        },
        "permutation_ledger": {
            "global_replicate_count": len(global_orders),
            "global_ledger_digest_sha256": global_ledger_digest,
            "era4_replicate_count": len(era4_orders),
            "era4_ledger_digest_sha256": era4_ledger_digest,
            "reverse_global_replicate_count": len(reverse_orders),
            "reverse_global_ledger_digest_sha256": reverse_ledger_digest,
        },
    }


def _holm_pair(raw_p_edge1: float, raw_p_edge2: float) -> tuple[float, float]:
    result = shared.holm_adjust((raw_p_edge1, raw_p_edge2))
    return result.holm_adjusted_p_values[0], result.holm_adjusted_p_values[1]


def _classify(
    global_holm: float, era4_holm: float, timing_pass: bool, directionality_pass: bool
) -> str:
    if global_holm <= 0.05 and era4_holm <= 0.05 and timing_pass and directionality_pass:
        return "SIGNAL"
    if global_holm <= 0.10:
        return "WEAK_SIGNAL"
    if global_holm > 0.10:
        return "NO_SIGNAL"
    raise te.Eh02DesignError("STOP_MULTIPLICITY_CONTRACT_BREACH: no classification rule matched")


def run(locked: dict[str, Any]) -> dict[str, Any]:
    t_start = time.perf_counter()

    fixture_values = run_synthetic_fixture_check()

    from lottolab.research.b649_eh01_eh10_dataset import load_clean_b649_history

    b649 = load_clean_b649_history()
    t539 = dataset.load_t539_history()
    p638z1 = dataset.load_p638_zone1_history()
    verify_dataset_identity(locked, b649, t539, p638z1)

    b649_bins_b3 = te.causal_tertile_bins(
        b649.main_number_sums,
        b649.draw_ids,
        edge_context=te.TARGET_SELF_CONTEXT,
        lottery="BIG_LOTTO",
    )
    b649_bins_b2 = te.causal_tertile_bins(
        b649.main_number_sums,
        b649.draw_ids,
        edge_context=te.TARGET_SELF_CONTEXT,
        lottery="BIG_LOTTO",
        bin_count=te.ALTERNATE_BIN_COUNT,
    )
    t539_bins_b3 = te.causal_tertile_bins(
        t539.main_number_sums, t539.draw_ids, edge_context=te.SOURCE_CONTEXT, lottery="DAILY_539"
    )
    t539_bins_b2 = te.causal_tertile_bins(
        t539.main_number_sums,
        t539.draw_ids,
        edge_context=te.SOURCE_CONTEXT,
        lottery="DAILY_539",
        bin_count=te.ALTERNATE_BIN_COUNT,
    )
    p638z1_bins_b3 = te.causal_tertile_bins(
        p638z1.main_number_sums,
        p638z1.draw_ids,
        edge_context=te.SOURCE_CONTEXT,
        lottery="POWER_LOTTO_ZONE1",
    )
    p638z1_bins_b2 = te.causal_tertile_bins(
        p638z1.main_number_sums,
        p638z1.draw_ids,
        edge_context=te.SOURCE_CONTEXT,
        lottery="POWER_LOTTO_ZONE1",
        bin_count=te.ALTERNATE_BIN_COUNT,
    )

    edge1 = compute_edge(
        forward_edge_id=te.EDGE_T539_TO_B649,
        reverse_edge_id=te.EDGE_B649_TO_T539_REVERSE,
        target_dates=b649.draw_dates,
        target_draw_ids=b649.draw_ids,
        target_bins_b3=b649_bins_b3,
        target_bins_b2=b649_bins_b2,
        source_dates=t539.draw_dates,
        source_draw_ids=t539.draw_ids,
        source_bins_b3=t539_bins_b3,
        source_bins_b2=t539_bins_b2,
        expected_eligible=locked["edge_1_expected_eligible_post_burn_in"],
        expected_era4_sizes=locked["edge_1_expected_era4_partition_sizes"],
    )
    edge2 = compute_edge(
        forward_edge_id=te.EDGE_P638Z1_TO_B649,
        reverse_edge_id=te.EDGE_B649_TO_P638Z1_REVERSE,
        target_dates=b649.draw_dates,
        target_draw_ids=b649.draw_ids,
        target_bins_b3=b649_bins_b3,
        target_bins_b2=b649_bins_b2,
        source_dates=p638z1.draw_dates,
        source_draw_ids=p638z1.draw_ids,
        source_bins_b3=p638z1_bins_b3,
        source_bins_b2=p638z1_bins_b2,
        expected_eligible=locked["edge_2_expected_eligible_post_burn_in"],
        expected_era4_sizes=locked["edge_2_expected_era4_partition_sizes"],
    )

    global_holm_1, global_holm_2 = _holm_pair(
        edge1["primary"]["global_raw_p"], edge2["primary"]["global_raw_p"]
    )
    era4_holm_1, era4_holm_2 = _holm_pair(
        edge1["primary"]["era4_raw_p"], edge2["primary"]["era4_raw_p"]
    )

    edge1["multiplicity"] = {"global_holm_p": global_holm_1, "era4_holm_p": era4_holm_1}
    edge2["multiplicity"] = {"global_holm_p": global_holm_2, "era4_holm_p": era4_holm_2}

    edge1["classification"] = _classify(
        global_holm_1,
        era4_holm_1,
        edge1["timing_control"]["pass"],
        edge1["directionality_control"]["pass"],
    )
    edge2["classification"] = _classify(
        global_holm_2,
        era4_holm_2,
        edge2["timing_control"]["pass"],
        edge2["directionality_control"]["pass"],
    )

    total_seconds = time.perf_counter() - t_start

    what_is_supported = [
        f"EDGE_1_{edge1['classification']}" if edge1["classification"] == "SIGNAL" else None,
        f"EDGE_2_{edge2['classification']}" if edge2["classification"] == "SIGNAL" else None,
    ]
    what_is_supported = [item for item in what_is_supported if item] or [
        "NONE_AT_THE_LOCKED_SIGNAL_THRESHOLD"
    ]

    return {
        "task_id": locked["task_id"],
        "variant_id": locked["variant_id"],
        "preregistration_hash_sha256": canonical_json.sha256_hex(
            canonical_json.canonical_bytes(locked)
        ),
        "synthetic_fixture_check": {"status": "PASS", "values": fixture_values},
        "data_authority": {
            "dataset_a": {
                "source_path": b649.source_path,
                "row_count": b649.row_count,
                "date_range": [b649.draw_dates[0], b649.draw_dates[-1]],
                "logical_sha256": b649.logical_sha256,
            },
            "dataset_b": {
                "source_path": t539.source_path,
                "row_count": t539.row_count,
                "date_range": [t539.draw_dates[0], t539.draw_dates[-1]],
                "logical_sha256": t539.logical_sha256,
            },
            "dataset_c": {
                "source_path": p638z1.source_path,
                "row_count": p638z1.row_count,
                "date_range": [p638z1.draw_dates[0], p638z1.draw_dates[-1]],
                "logical_sha256": p638z1.logical_sha256,
            },
        },
        "edge_1_t539_to_b649": edge1,
        "edge_2_p638z1_to_b649": edge2,
        "joint_interpretation": {
            "combined_effect_computed": False,
            "edges_are_separate_holm_families_within_shared_global_and_era4_families": True,
            "what_is_supported": what_is_supported,
            "what_is_not_supported": [
                "predictive_advantage",
                "allocation_benefit",
                "prize_value_advantage",
                "universal_cross_lottery_causality",
                "arbitrary_lag_generalization",
                "combined_edge_effect",
            ],
        },
        "scope": {
            "predictive_advantage": "NOT_TESTED",
            "allocation_benefit": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "production_promotion": "NO",
            "cohort_creation": "NO",
            "prospective_activation": "NO",
            "parameter_rescue_run": "NO",
            "new_predictive_claim": "NO",
        },
        "runtime_seconds": total_seconds,
    }


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    RESULT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {RESULT_PATH}")
    edge1_result = result["edge_1_t539_to_b649"]
    edge2_result = result["edge_2_p638z1_to_b649"]
    print(f"EDGE_1 (T539->B649) classification: {edge1_result['classification']}")
    print(f"EDGE_2 (P638Z1->B649) classification: {edge2_result['classification']}")
    print(f"total runtime: {result['runtime_seconds']:.1f}s")


if __name__ == "__main__":
    main()
