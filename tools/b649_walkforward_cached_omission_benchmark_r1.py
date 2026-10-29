"""Compare original and cache-backed low-overlap K5 cutoff workloads."""

from __future__ import annotations

import json
from random import Random
from statistics import median
from time import perf_counter

from lottolab.research import b649_walkforward_incremental_cache_r1 as _cache
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _multiscale,
)
from lottolab.research.b649_walkforward_cached_omission_adapter_r1 import (
    LOW_OVERLAP_K5_CANDIDATE_ID,
    B649WalkForwardCachedOmissionAdapter,
)

_DRAW_COUNT = 1010
_SEED = 10281028
_REPETITIONS = 3
_SOURCE_ID = "benchmark:b649-multiscale-omission-low-overlap-k5:r1"


def _fixed_draws() -> tuple[tuple[int, ...], ...]:
    generator = Random(_SEED)
    return tuple(
        tuple(sorted(generator.sample(range(1, 50), 6))) for _ in range(_DRAW_COUNT)
    )


def _original_workload(
    draws: tuple[tuple[int, ...], ...], cutoffs: range
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    return tuple(
        _multiscale.produce_biglotto_multiscale_omission_pressure_multi_ticket_candidate(
            LOW_OVERLAP_K5_CANDIDATE_ID,
            draws,
            target_index,
        )
        for target_index in cutoffs
    )


def _cached_workload(
    draws: tuple[tuple[int, ...], ...], cutoffs: range
) -> tuple[
    tuple[tuple[tuple[int, ...], ...], ...],
    _cache.B649WalkForwardCacheInfo,
]:
    history = _cache.B649WalkForwardHistory.from_draws(_SOURCE_ID, draws)
    adapter = B649WalkForwardCachedOmissionAdapter(
        _cache.B649WalkForwardIncrementalCache()
    )
    outputs = tuple(
        adapter.produce_low_overlap_k5(history, target_index)
        for target_index in cutoffs
    )
    return outputs, adapter.cache.cache_info


def main() -> None:
    draws = _fixed_draws()
    cutoffs = range(750, len(draws))
    original_seconds: list[float] = []
    cached_seconds: list[float] = []
    final_cache_info: _cache.B649WalkForwardCacheInfo | None = None

    for _ in range(_REPETITIONS):
        started = perf_counter()
        original_outputs = _original_workload(draws, cutoffs)
        original_seconds.append(perf_counter() - started)

        started = perf_counter()
        cached_outputs, final_cache_info = _cached_workload(draws, cutoffs)
        cached_seconds.append(perf_counter() - started)

        if cached_outputs != original_outputs:
            raise AssertionError("cached K5 output differs from the original producer")

    if final_cache_info is None:
        raise AssertionError("benchmark did not execute a cached workload")

    original_median = median(original_seconds)
    cached_median = median(cached_seconds)
    result = {
        "workload": {
            "dataset_draw_count": _DRAW_COUNT,
            "dataset_generation": f"Random({_SEED}), six unique numbers from 1..49",
            "cutoff_indices_inclusive": [750, _DRAW_COUNT - 1],
            "cutoff_count": len(cutoffs),
            "strategy": "B649_CANDIDATE_SET_LOW_OVERLAP_V1, K=5",
            "repetitions": _REPETITIONS,
            "cached_runtime_includes_history_snapshot_and_cache_creation": True,
        },
        "parity": {"ordered_k5_portfolios_all_cutoffs": True},
        "original_seconds": original_seconds,
        "cached_seconds": cached_seconds,
        "original_median_seconds": original_median,
        "cached_median_seconds": cached_median,
        "measured_speedup": original_median / cached_median,
        "last_cached_run_cache_info": {
            "hits": final_cache_info.hits,
            "misses": final_cache_info.misses,
            "entries": final_cache_info.entries,
            "incremental_draw_updates": final_cache_info.incremental_draw_updates,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
