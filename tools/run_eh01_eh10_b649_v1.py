"""Execute the locked EH01_MATRIX_PROFILE_MOTIF_DISCORD_B649_V1 and
EH10_PERMUTATION_ENTROPY_ORDINAL_B649_V1 experiment.

Reads locked parameters from
`docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-preregistration-hash.json`
and re-verifies that file's hash before using anything in it (same
fail-closed pattern every prior lock-and-execute script in this project
uses; see `run_greedy_min_overlap_constructor_p638_zone1_v1.py`). Loads the
sealed B649 baseline read-only and refuses to run if its identity does not
exactly match the locked dataset identity
(`STOP_DATASET_AUTHORITY_MISMATCH`).

`GLOBAL` and `ERA4` surrogates are generated once per replicate and reused
for *both* EH01 and EH10 (same seed, same hash-sort mechanism) -- an
efficiency/reproducibility choice, not a combined-family shortcut: EH01 and
EH10 remain fully separate Holm families and are classified independently
(`STOP_OUT_OF_SCOPE_HYPOTHESIS` would apply to computing a combined
EH01+EH10 effect, which this script never does).

Parallelized across independent permutation replicates via stdlib
`multiprocessing` -- an execution-engineering choice that changes wall-clock
only, never a locked statistic, seed, or ordering.
"""

from __future__ import annotations

import json
import multiprocessing
import statistics
import time
from pathlib import Path
from typing import Any

from lottolab.evidence import canonical_json
from lottolab.research import b649_eh01_eh10_shared as shared
from lottolab.research import b649_eh01_matrix_profile as eh01
from lottolab.research import b649_eh10_permutation_entropy as eh10
from lottolab.research.b649_eh01_eh10_dataset import load_clean_b649_history

PREREGISTRATION_HASH_PATH = Path(
    "docs/research/matrix-native-results/"
    "eh01-eh10-b649-ordinal-temporal-v1-preregistration-hash.json"
)
RESULT_PATH = Path(
    "docs/research/matrix-native-results/eh01-eh10-b649-ordinal-temporal-v1-result.json"
)

LENGTHS = (26, 52, 104)
ORDERS = (3, 4, 5)
WINDOW = 124
PERMUTATIONS = 999
EH01_ENDPOINTS = tuple(f"{stat}_{m}" for m in LENGTHS for stat in ("motif", "discord"))
EH10_ENDPOINTS = tuple(f"pe_{d}" for d in ORDERS)


def load_locked_parameters() -> dict[str, Any]:
    record = json.loads(PREREGISTRATION_HASH_PATH.read_text(encoding="utf-8"))
    locked = record["locked_parameters"]
    recomputed = canonical_json.sha256_hex(canonical_json.canonical_bytes(locked))
    if recomputed != record["preregistration_hash_sha256"]:
        raise ValueError(
            "STOP_SPEC_AUTHORITY_MISMATCH: preregistration hash mismatch -- the locked "
            "parameters file was modified after locking; refusing to execute"
        )
    return locked


def verify_dataset_identity(locked: dict[str, Any], history: Any) -> None:
    mismatches: list[str] = []
    if history.row_count != locked["dataset_row_count"]:
        mismatches.append(f"row_count {history.row_count} != {locked['dataset_row_count']}")
    if history.excluded_date_like_contaminants != locked["dataset_excluded_contaminant_count"]:
        mismatches.append("excluded_date_like_contaminants mismatch")
    if history.draw_dates[0] != locked["dataset_date_range_start"]:
        mismatches.append("date_range_start mismatch")
    if history.draw_dates[-1] != locked["dataset_date_range_end"]:
        mismatches.append("date_range_end mismatch")
    if history.logical_sha256 != locked["dataset_logical_sha256"]:
        mismatches.append("logical_sha256 mismatch")
    if history.draw_data_version != locked["dataset_draw_data_version"]:
        mismatches.append("draw_data_version mismatch")
    if mismatches:
        raise ValueError("STOP_DATASET_AUTHORITY_MISMATCH: " + "; ".join(mismatches))


# ---- worker process state (set once per worker by the Pool initializer) ----
_STATE: dict[str, Any] = {}


def _init_worker(draw_ids: tuple[int, ...], values: tuple[int, ...]) -> None:
    _STATE["draw_ids"] = draw_ids
    _STATE["values"] = values


def _profile_stats(values_slice: tuple[int, ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in LENGTHS:
        profile = eh01.causal_profile(values_slice, m)
        out[f"motif_{m}"] = profile.motif_statistic
        out[f"discord_{m}"] = profile.discord_statistic
    return out


def _entropy_stats(
    values_slice: tuple[int, ...], draw_ids_slice: tuple[int, ...]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for d in ORDERS:
        result = eh10.rolling_permutation_entropy(
            values_slice, draw_ids_slice, order=d, window=WINDOW
        )
        out[f"pe_{d}"] = result.statistic
    return out


def _global_replicate(replicate: int) -> dict[str, Any]:
    draw_ids = _STATE["draw_ids"]
    values = _STATE["values"]
    order = shared.global_surrogate_order(draw_ids, replicate)
    surrogate_values = shared.apply_order(values, order)
    surrogate_draw_ids = shared.apply_order(draw_ids, order)
    return {
        "replicate": replicate,
        "order": order,
        "eh01": _profile_stats(surrogate_values),
        "eh10": _entropy_stats(surrogate_values, surrogate_draw_ids),
    }


def _era4_replicate(replicate: int) -> dict[str, Any]:
    draw_ids = _STATE["draw_ids"]
    values = _STATE["values"]
    n = len(values)
    order = shared.era4_surrogate_order(draw_ids, replicate)
    surrogate_values = shared.apply_order(values, order)
    surrogate_draw_ids = shared.apply_order(draw_ids, order)

    era_local: list[dict[str, Any]] = []
    for era_number, (first, last) in enumerate(shared.era4_bounds(n), start=1):
        era_values = surrogate_values[first - 1 : last]
        era_draw_ids = surrogate_draw_ids[first - 1 : last]
        era_local.append(
            {
                "era": era_number,
                "eh01": _profile_stats(era_values),
                "eh10": _entropy_stats(era_values, era_draw_ids),
            }
        )

    return {
        "replicate": replicate,
        "order": order,
        "eh01": _profile_stats(surrogate_values),
        "eh10": _entropy_stats(surrogate_values, surrogate_draw_ids),
        "era_local": era_local,
    }


def _observed_stats(history: Any) -> dict[str, Any]:
    values = history.main_number_sums
    draw_ids = history.draw_ids
    n = len(values)
    era_local: list[dict[str, Any]] = []
    for era_number, (first, last) in enumerate(shared.era4_bounds(n), start=1):
        era_values = values[first - 1 : last]
        era_draw_ids = draw_ids[first - 1 : last]
        era_local.append(
            {
                "era": era_number,
                "eh01": _profile_stats(era_values),
                "eh10": _entropy_stats(era_values, era_draw_ids),
            }
        )
    return {
        "eh01": _profile_stats(values),
        "eh10": _entropy_stats(values, draw_ids),
        "era_local": era_local,
    }


def _percentile_summary(observed: float, surrogates: tuple[float, ...]) -> dict[str, Any]:
    sorted_surrogates = sorted(surrogates)
    at_or_below = sum(1 for value in sorted_surrogates if value <= observed)
    return {
        "surrogate_median": statistics.median(sorted_surrogates),
        "surrogate_q1": statistics.quantiles(sorted_surrogates, n=4)[0],
        "surrogate_q3": statistics.quantiles(sorted_surrogates, n=4)[2],
        "surrogate_min": sorted_surrogates[0],
        "surrogate_max": sorted_surrogates[-1],
        "observed_percentile_within_surrogates": at_or_below / len(sorted_surrogates),
    }


def _classify(
    endpoints: tuple[str, ...],
    global_holm: dict[str, float],
    era4_holm: dict[str, float],
) -> tuple[str, str | None]:
    signal_endpoint = None
    for endpoint in endpoints:
        if global_holm[endpoint] <= 0.05 and era4_holm[endpoint] <= 0.05:
            signal_endpoint = endpoint
            break
    if signal_endpoint is not None:
        return "SIGNAL", signal_endpoint

    weak_endpoint = None
    for endpoint in endpoints:
        if global_holm[endpoint] <= 0.10:
            weak_endpoint = endpoint
            break
    if weak_endpoint is not None:
        return "WEAK_SIGNAL", weak_endpoint

    if all(global_holm[endpoint] > 0.10 for endpoint in endpoints):
        return "NO_SIGNAL", None

    raise ValueError("STOP_MULTIPLICITY_CONTRACT_BREACH: no classification rule matched")


def run(locked: dict[str, Any]) -> dict[str, Any]:
    t_start = time.perf_counter()

    history = load_clean_b649_history()
    verify_dataset_identity(locked, history)

    draw_ids = history.draw_ids
    values = history.main_number_sums

    observed = _observed_stats(history)

    worker_count = max(1, (multiprocessing.cpu_count() or 2) - 1)
    print(f"running {2 * PERMUTATIONS} replicates across {worker_count} worker processes")

    t0 = time.perf_counter()
    with multiprocessing.Pool(
        processes=worker_count, initializer=_init_worker, initargs=(draw_ids, values)
    ) as pool:
        global_results = pool.map(_global_replicate, range(PERMUTATIONS), chunksize=1)
        era4_results = pool.map(_era4_replicate, range(PERMUTATIONS), chunksize=1)
    replicate_seconds = time.perf_counter() - t0
    print(f"replicate computation: {replicate_seconds:.1f}s")

    global_orders = tuple(r["order"] for r in global_results)
    era4_orders = tuple(r["order"] for r in era4_results)
    shared.assert_distinct_permutations(global_orders, policy=shared.GLOBAL_POLICY)
    shared.assert_distinct_permutations(era4_orders, policy=shared.ERA4_POLICY)
    global_ledger_digest = shared.permutation_ledger_digest(
        global_orders, policy=shared.GLOBAL_POLICY
    )
    era4_ledger_digest = shared.permutation_ledger_digest(era4_orders, policy=shared.ERA4_POLICY)

    def _global_nulls(hypothesis: str, endpoint: str) -> tuple[float, ...]:
        return tuple(r[hypothesis][endpoint] for r in global_results)

    def _era4_full_nulls(hypothesis: str, endpoint: str) -> tuple[float, ...]:
        return tuple(r[hypothesis][endpoint] for r in era4_results)

    def _era4_local_nulls(hypothesis: str, era_number: int, endpoint: str) -> tuple[float, ...]:
        return tuple(
            r["era_local"][era_number - 1][hypothesis][endpoint] for r in era4_results
        )

    def _endpoint_block(
        hypothesis: str, endpoints: tuple[str, ...]
    ) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
        raw_global = [
            shared.raw_p_value(observed[hypothesis][e], _global_nulls(hypothesis, e))
            for e in endpoints
        ]
        raw_era4 = [
            shared.raw_p_value(observed[hypothesis][e], _era4_full_nulls(hypothesis, e))
            for e in endpoints
        ]
        holm_global = shared.holm_adjust(tuple(raw_global))
        holm_era4 = shared.holm_adjust(tuple(raw_era4))

        global_holm_by_endpoint = dict(
            zip(endpoints, holm_global.holm_adjusted_p_values, strict=True)
        )
        era4_holm_by_endpoint = dict(
            zip(endpoints, holm_era4.holm_adjusted_p_values, strict=True)
        )

        endpoint_details: dict[str, Any] = {}
        for index, endpoint in enumerate(endpoints):
            global_summary = _percentile_summary(
                observed[hypothesis][endpoint], _global_nulls(hypothesis, endpoint)
            )
            era4_summary = _percentile_summary(
                observed[hypothesis][endpoint], _era4_full_nulls(hypothesis, endpoint)
            )
            endpoint_details[endpoint] = {
                "observed": observed[hypothesis][endpoint],
                "global_raw_p": raw_global[index],
                "global_holm_p": holm_global.holm_adjusted_p_values[index],
                "global_surrogate_summary": global_summary,
                "era4_raw_p": raw_era4[index],
                "era4_holm_p": holm_era4.holm_adjusted_p_values[index],
                "era4_surrogate_summary": era4_summary,
            }
        return endpoint_details, global_holm_by_endpoint, era4_holm_by_endpoint

    eh01_endpoint_details, eh01_global_holm, eh01_era4_holm = _endpoint_block(
        "eh01", EH01_ENDPOINTS
    )
    eh10_endpoint_details, eh10_global_holm, eh10_era4_holm = _endpoint_block(
        "eh10", EH10_ENDPOINTS
    )

    eh01_classification, eh01_signal_endpoint = _classify(
        EH01_ENDPOINTS, eh01_global_holm, eh01_era4_holm
    )
    eh10_classification, eh10_signal_endpoint = _classify(
        EH10_ENDPOINTS, eh10_global_holm, eh10_era4_holm
    )

    def _era_diagnostics(hypothesis: str, endpoints: tuple[str, ...]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for era_number in (1, 2, 3, 4):
            era_observed = observed["era_local"][era_number - 1][hypothesis]
            per_endpoint: dict[str, Any] = {}
            for endpoint in endpoints:
                nulls = _era4_local_nulls(hypothesis, era_number, endpoint)
                summary = _percentile_summary(era_observed[endpoint], nulls)
                per_endpoint[endpoint] = {"observed": era_observed[endpoint], **summary}
            blocks.append({"era": era_number, "endpoints": per_endpoint})
        return blocks

    eh01_era_diagnostics = _era_diagnostics("eh01", EH01_ENDPOINTS)
    eh10_era_diagnostics = _era_diagnostics("eh10", EH10_ENDPOINTS)

    total_seconds = time.perf_counter() - t_start

    return {
        "task_id": locked["task_id"],
        "eh01_variant_id": locked["eh01_variant_id"],
        "eh10_variant_id": locked["eh10_variant_id"],
        "preregistration_hash_sha256": canonical_json.sha256_hex(
            canonical_json.canonical_bytes(locked)
        ),
        "data_authority": {
            "source_path": history.source_path,
            "draw_data_version": history.draw_data_version,
            "row_count": history.row_count,
            "excluded_date_like_contaminants": history.excluded_date_like_contaminants,
            "date_range": [history.draw_dates[0], history.draw_dates[-1]],
            "logical_sha256": history.logical_sha256,
        },
        "permutation_ledger": {
            "global_replicate_count": len(global_orders),
            "global_all_distinct": True,
            "global_ledger_digest_sha256": global_ledger_digest,
            "era4_replicate_count": len(era4_orders),
            "era4_all_distinct": True,
            "era4_ledger_digest_sha256": era4_ledger_digest,
        },
        "eh01": {
            "lengths": list(LENGTHS),
            "endpoints": eh01_endpoint_details,
            "era_local_diagnostics": eh01_era_diagnostics,
            "classification": eh01_classification,
            "signal_endpoint": eh01_signal_endpoint,
            "comparator_decision": "REMOVE_UNIDENTIFIABLE_FROZEN_STRATEGY_COMPARATOR_NO_PROXY",
            "claim_scope": "STRUCTURAL_TEMPORAL_PRECONDITION_ONLY",
        },
        "eh10": {
            "orders": list(ORDERS),
            "window": WINDOW,
            "endpoints": eh10_endpoint_details,
            "era_local_diagnostics": eh10_era_diagnostics,
            "classification": eh10_classification,
            "signal_endpoint": eh10_signal_endpoint,
            "claim_scope": "ORDINAL_STRUCTURAL_PRECONDITION_ONLY",
        },
        "joint_interpretation": {
            "combined_effect_computed": False,
            "eh01_and_eh10_are_separate_holm_families": True,
            "what_is_supported": _what_is_supported(eh01_classification, eh10_classification),
            "what_is_not_supported": [
                "predictive_advantage",
                "allocation_benefit",
                "prize_value_advantage",
                "economic_optimality",
                "combined_eh01_eh10_effect",
            ],
        },
        "scope": {
            "predictive_advantage": "NOT_TESTED",
            "allocation_benefit": "NOT_TESTED",
            "prize_value_advantage": "NOT_TESTED",
            "economic_optimality": "NOT_TESTED",
            "production_promotion": "NO",
            "cohort_creation": "NO",
            "prospective_activation": "NO",
            "parameter_rescue_run": "NO",
            "oof_proxy_used": "NO",
            "new_predictive_claim": "NO",
        },
        "runtime_seconds": {
            "replicate_computation": replicate_seconds,
            "total": total_seconds,
        },
        "worker_count": worker_count,
    }


def _what_is_supported(eh01_classification: str, eh10_classification: str) -> list[str]:
    supported: list[str] = []
    if eh01_classification == "SIGNAL":
        supported.append("EH01_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_AND_HORIZON")
    if eh10_classification == "SIGNAL":
        supported.append(
            "EH10_ORDINAL_STRUCTURAL_SIGNAL_AT_LOCKED_REPRESENTATION_ORDER_AND_WINDOW"
        )
    if not supported:
        supported.append("NONE_AT_THE_LOCKED_SIGNAL_THRESHOLD")
    return supported


def main() -> None:
    locked = load_locked_parameters()
    result = run(locked)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True).rstrip("\n") + "\n"
    RESULT_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {RESULT_PATH}")
    eh01_cls, eh01_ep = result["eh01"]["classification"], result["eh01"]["signal_endpoint"]
    eh10_cls, eh10_ep = result["eh10"]["classification"], result["eh10"]["signal_endpoint"]
    print(f"EH01 classification: {eh01_cls} ({eh01_ep})")
    print(f"EH10 classification: {eh10_cls} ({eh10_ep})")
    print(f"total runtime: {result['runtime_seconds']['total']:.1f}s")


if __name__ == "__main__":
    main()
