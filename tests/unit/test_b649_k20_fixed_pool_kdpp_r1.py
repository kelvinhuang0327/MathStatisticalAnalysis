"""Toy mathematical checks and isolated mocked budget/resumption tests.

No test draws a sample from the real 46-ticket pool or invokes a real scorer.
"""

from __future__ import annotations

import itertools
import json
from collections import Counter
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from lottolab.research import b649_k20_fixed_pool_kdpp_r1 as study


def toy_kernel() -> study.FloatArray:
    u = np.array([0.25, 0.5, 0.75, 1.0], dtype=np.float64)
    return np.diag(np.array([1.0, 2.0, 3.0, 4.0])) + np.outer(u, u)


def test_esp_equals_enumerated_principal_minors() -> None:
    kernel = toy_kernel()
    prepared = study.prepare_kernel(kernel, 2)
    expected = sum(
        float(np.linalg.det(kernel[np.ix_(a, a)])) for a in itertools.combinations(range(4), 2)
    )
    assert prepared.esp[2, 4] == pytest.approx(expected, rel=1e-13)


def test_nondiagonal_toy_distribution_and_fixed_size() -> None:
    kernel = toy_kernel()
    prepared = study.prepare_kernel(kernel, 2)
    subsets = list(itertools.combinations(range(4), 2))
    weights = np.array([np.linalg.det(kernel[np.ix_(a, a)]) for a in subsets])
    probabilities = weights / weights.sum()
    rng = np.random.RandomState(20261023)
    counts: Counter[tuple[int, ...]] = Counter()
    for _ in range(20000):
        sample = study.sample_kdpp(prepared, rng)
        assert len(sample) == 2 and len(set(sample)) == 2
        assert all(0 <= i < 4 for i in sample)
        counts[tuple(sorted(sample))] += 1
    total_variation = (
        sum(abs(counts[a] / 20000 - float(p)) for a, p in zip(subsets, probabilities, strict=True))
        / 2
    )
    print(f"TOY_DISTRIBUTION draws=20000 seed=20261023 TV={total_variation:.12g}")
    assert total_variation <= 0.03


def test_toy_reproducibility_and_rng_continuation() -> None:
    prepared = study.prepare_kernel(toy_kernel(), 2)
    first = np.random.RandomState(1337)
    second = np.random.RandomState(1337)
    assert [study.sample_kdpp(prepared, first) for _ in range(12)] == [
        study.sample_kdpp(prepared, second) for _ in range(12)
    ]
    restored = study.restore_rng(study.serialize_rng(first))
    assert [study.sample_kdpp(prepared, first) for _ in range(12)] == [
        study.sample_kdpp(prepared, restored) for _ in range(12)
    ]


@pytest.mark.parametrize(
    "kernel,k",
    [
        (np.diag([2.0, -1.0]), 1),
        (np.diag([1.0, 1e-30]), 2),
        (np.array([[1.0, np.nan], [np.nan, 1.0]]), 1),
        (np.array([[1.0, 0.2], [0.0, 1.0]]), 1),
        (np.eye(2, dtype=np.float32), 1),
    ],
)
def test_reject_invalid_kernel(kernel: study.FloatArray, k: int) -> None:
    with pytest.raises(ValueError):
        study.prepare_kernel(kernel, k)


@pytest.mark.parametrize(
    "tickets",
    [
        [[True, 2, 3, 4, 5, 6]],
        [[0, 2, 3, 4, 5, 6]],
        [[1, 2, 3, 4, 5, 50]],
        [[1, 2, 3, 4, 5]],
        [[1, 2, 3, 4, 5, 5]],
        [[1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]],
    ],
)
def test_reject_illegal_or_duplicate_tickets(tickets: list[list[int]]) -> None:
    with pytest.raises(ValueError):
        study.canonicalize(tickets)


def test_canonical_identity_is_order_independent() -> None:
    first = study.canonicalize([(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)])
    second = study.canonicalize([(12, 11, 10, 9, 8, 7), (6, 5, 4, 3, 2, 1)])
    assert study.canonical_bytes(first) == study.canonical_bytes(second)


def test_pinned_sources_and_formal_kernel_without_sampling() -> None:
    pool = study.load_fixed_pool()
    assert len(pool.tickets) == 46
    assert study.digest(study.canonical_bytes(pool.tickets)) == study.POOL_SHA
    prepared = study.prepare_kernel(study.fixed_kernel(pool.tickets), 20)
    assert prepared.diagnostics["numerical_rank"] == 46
    assert prepared.diagnostics["max_symmetry_error"] == 0
    assert prepared.values.min() > 0


def mock_pool() -> study.FixedPool:
    tickets = tuple(itertools.islice(itertools.combinations(range(1, 11), 6), 30))
    return study.FixedPool(tickets, {"V7": tickets[:20]}, {"identity": "SYNTHETIC_MOCK_ONLY"})


def initialize(directory: Path) -> None:
    study.write_json(
        directory / "result.json",
        {
            "TASK_ID": study.TASK_ID,
            "phase": "IMPLEMENTATION",
            "TASK_STATUS": "IN_PROGRESS",
            "RAW_DRAW_ATTEMPTS": 0,
            "RAW_DRAW_COMPLETED": 0,
            "FORMAL_EXACT_ATTEMPTS": 0,
            "FORMAL_EXACT_COMPLETED": 0,
            "raw_calls": [],
            "exact_calls": [],
            "rng_state": None,
        },
    )


def test_mock_four_attempts_existing_duplicate_pruned_and_no_refill(tmp_path: Path) -> None:
    initialize(tmp_path)
    pool = mock_pool()
    existing = list(range(20))
    new = list(range(1, 21))
    pruned = list(range(2, 22))
    proposals = iter([existing, new, list(reversed(new)), pruned])
    events: list[str] = []

    def sampler(_: np.random.RandomState) -> list[int]:
        receipt = json.loads((tmp_path / "result.json").read_text())
        assert receipt["raw_calls"][-1]["status"] == "IN_PROGRESS"
        events.append("sample")
        return next(proposals)

    def u3(portfolio: study.Portfolio) -> tuple[int, int, int]:
        assert events.count("sample") == 4
        events.append("u3")
        return (study.REFERENCE + (1 if portfolio[0] == pool.tickets[1] else -1), 0, 0)

    def scorer(_: study.Portfolio) -> tuple[int, study.Json]:
        receipt = json.loads((tmp_path / "result.json").read_text())
        assert receipt["exact_calls"][-1]["status"] == "IN_PROGRESS"
        assert events.count("u3") == 2
        events.append("exact")
        return study.REFERENCE, {"actual_engine": "enumeration", "fallback_reason": None}

    result = study.run_bounded(tmp_path, pool, sampler, u3, scorer)
    assert result["RAW_DRAW_ATTEMPTS"] == 4
    assert result["EXCLUDED_EXISTING_COUNT"] == 1
    assert result["DUPLICATE_COUNT"] == 1
    assert result["DISTINCT_NEW_CANDIDATE_COUNT"] == 2
    assert result["U3_PRUNED_COUNT"] == 1
    assert result["FORMAL_EXACT_ATTEMPTS"] == 1
    records = result["raw_records"]
    assert [r["status"] for r in records] == [
        "EXCLUDED_EXISTING",
        "EXACT_COMPLETE",
        "DUPLICATE",
        "SAFE_PRUNED",
    ]
    assert records[3]["exact_count"] is None
    assert records[1]["delta_win7"] == 0
    before = events.copy()
    study.run_bounded(tmp_path, pool, sampler, u3, scorer)
    assert events == before  # completed study is reused, never replayed


@pytest.mark.parametrize("offset,expected_exact", [(-1, 0), (0, 0), (1, 4)])
def test_u3_boundaries_and_exact_limit(tmp_path: Path, offset: int, expected_exact: int) -> None:
    initialize(tmp_path)
    sequence = iter([list(range(i, i + 20)) for i in range(1, 5)])
    exact_count = 0

    def scorer(_: study.Portfolio) -> tuple[int, study.Json]:
        nonlocal exact_count
        exact_count += 1
        return study.REFERENCE + 1, {"actual_engine": "enumeration", "fallback_reason": None}

    result = study.run_bounded(
        tmp_path,
        mock_pool(),
        lambda _: next(sequence),
        lambda _: (study.REFERENCE + offset, 0, 0),
        scorer,
    )
    assert exact_count == expected_exact
    assert result["RAW_DRAW_ATTEMPTS"] == 4
    assert result["FORMAL_EXACT_ATTEMPTS"] == expected_exact
    if expected_exact:
        assert all(r["delta_win7"] == 1 for r in result["raw_records"])
        assert result["K20_GAIN_ESTABLISHED"] == "YES"
    else:
        assert all(r["exact_count"] is None for r in result["raw_records"])


def test_uncertain_reserved_raw_is_never_replayed(tmp_path: Path) -> None:
    initialize(tmp_path)
    calls = 0

    def failing(_: np.random.RandomState) -> list[int]:
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic interruption after reservation")

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        study.run_bounded(tmp_path, mock_pool(), failing, lambda _: (0, 0, 0), lambda _: (0, {}))
    with pytest.raises(study.IncompleteCall, match="uncertain completion"):
        study.run_bounded(tmp_path, mock_pool(), failing, lambda _: (0, 0, 0), lambda _: (0, {}))
    assert calls == 1
    receipt = cast(study.Json, json.loads((tmp_path / "result.json").read_text()))
    assert receipt["RAW_DRAW_ATTEMPTS"] == 1
    assert (tmp_path / "result.before_1.json").exists()
    assert (tmp_path / "result.before_2.json").exists()


def test_uncertain_reserved_exact_is_never_replayed(tmp_path: Path) -> None:
    initialize(tmp_path)
    sequence = iter([list(range(i, i + 20)) for i in range(1, 5)])
    calls = 0

    def failing(_: study.Portfolio) -> tuple[int, study.Json]:
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic Exact interruption")

    with pytest.raises(RuntimeError, match="synthetic Exact interruption"):
        study.run_bounded(
            tmp_path,
            mock_pool(),
            lambda _: next(sequence),
            lambda _: (study.REFERENCE + 1, 0, 0),
            failing,
        )
    with pytest.raises(study.IncompleteCall, match="uncertain completion"):
        study.run_bounded(
            tmp_path,
            mock_pool(),
            lambda _: next(sequence),
            lambda _: (study.REFERENCE + 1, 0, 0),
            failing,
        )
    assert calls == 1
    receipt = json.loads((tmp_path / "result.json").read_text())
    assert receipt["RAW_DRAW_ATTEMPTS"] == 4
    assert receipt["FORMAL_EXACT_ATTEMPTS"] == 1


def test_resume_uses_completed_raw_and_only_three_remaining_attempts(tmp_path: Path) -> None:
    initialize(tmp_path)
    pool = mock_pool()
    indices = list(range(1, 21))
    portfolio = study.canonicalize(tuple(pool.tickets[i] for i in indices), 20)
    sha = study.digest(study.canonical_bytes(portfolio))
    receipt = cast(study.Json, json.loads((tmp_path / "result.json").read_text()))
    receipt.update(
        RAW_DRAW_ATTEMPTS=1,
        RAW_DRAW_COMPLETED=1,
        raw_calls=[{"ordinal": 1, "status": "COMPLETE", "sha256": sha}],
        rng_state=study.serialize_rng(np.random.RandomState(42)),
    )
    study.write_json(tmp_path / "result.json", receipt)
    study.write_json(
        tmp_path / "candidates.json",
        {
            "source_manifest": pool.manifest,
            "raw_records": [
                {
                    "ordinal": 1,
                    "raw_indices": indices,
                    "tickets": portfolio,
                    "sha256": sha,
                    "status": "RAW_COMPLETE",
                    "u3": None,
                    "exact_count": None,
                }
            ],
        },
    )
    calls = 0

    def sampler(_: np.random.RandomState) -> list[int]:
        nonlocal calls
        calls += 1
        return list(range(calls + 1, calls + 21))

    def forbidden(_: study.Portfolio) -> tuple[int, study.Json]:
        raise AssertionError("pruned candidate must not be scored")

    result = study.run_bounded(tmp_path, pool, sampler, lambda _: (0, 0, 0), forbidden)
    assert calls == 3
    assert result["RAW_DRAW_ATTEMPTS"] == 4
    assert result["raw_records"][0]["sha256"] == sha
    assert result["FORMAL_EXACT_ATTEMPTS"] == 0
