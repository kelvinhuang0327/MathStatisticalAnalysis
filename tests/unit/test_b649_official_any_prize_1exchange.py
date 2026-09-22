"""Structural oracles for the frozen candidate; no historical outcomes or RNG.

The arithmetic ticket fixture is synthetic. Its seed ranks below were observed
by invoking the unmodified B649_DETERMINISTIC_MIN_OVERLAP 1.0.0 at commit
fbed3da52e4b6b8907afe71eed52e802b51a5cb0 (source blob 4178aaf1322e81f5249914312c7582a5ae76aae0).
The donor's ranked pool was asserted identical before comparing its output.
The donor checkout and application modules are not needed by these tests.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import json
import random
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from lottolab.research import b649_official_any_prize_1exchange as candidate
from lottolab.research import b649_official_any_prize_exact as exact

type Ranks = tuple[int, ...]
type Portfolio = tuple[tuple[int, ...], ...]

POOL: Portfolio = tuple(
    tuple(sorted(1 + (11 * i + j * j + 3 * j) % 49 for j in range(6))) for i in range(21)
)
DONOR_SEEDS: Mapping[int, Ranks] = {
    5: (1, 2, 3, 4, 5),
    10: (1, 2, 3, 4, 5, 6, 7, 8, 10, 11),
    20: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21),
}


def _install_scores(
    monkeypatch: pytest.MonkeyPatch,
    pool: Portfolio,
    scores: Mapping[Ranks, int],
    *,
    default: int = 90,
) -> list[Ranks]:
    """Mechanical search oracle only; the real-model tests below never use it."""
    rank_by_ticket = {ticket: rank for rank, ticket in enumerate(pool, 1)}
    calls: list[Ranks] = []

    def draws(pool_size: int, draw_size: int) -> exact.DrawMasks:
        assert (pool_size, draw_size) == (49, 6)
        return np.zeros(1, dtype=np.uint64)

    def evaluate(
        portfolio: Sequence[Sequence[int]],
        *,
        pool_size: int,
        draw_size: int,
        outright_matches: int,
        draws: exact.DrawMasks,
    ) -> exact.ExactPortfolioProbability:
        assert (pool_size, draw_size, outright_matches) == (49, 6, 3)
        assert draws.size == 1
        ranks = tuple(rank_by_ticket[tuple(ticket)] for ticket in portfolio)
        assert ranks == tuple(sorted(set(ranks)))
        calls.append(ranks)
        count = scores.get(ranks, default)
        # Deliberately conflicting M3+ direction: it must never select the move.
        return exact.ExactPortfolioProbability(1000, 43, 2 if count <= 100 else 1, count)

    monkeypatch.setattr(exact, "all_main_draw_masks", draws)
    monkeypatch.setattr(exact, "evaluate_portfolio", evaluate)
    return calls


def _prefix_seed(_pool: Portfolio, k: int, _repository: Path) -> Ranks:
    return tuple(range(1, k + 1))


@pytest.mark.parametrize("k", (5, 10, 20))
@pytest.mark.parametrize("reverse", (False, True))
def test_original_seed_authority_reused_without_reordering(
    monkeypatch: pytest.MonkeyPatch, k: int, reverse: bool
) -> None:
    pool = POOL[: k + 1][::-1] if reverse else POOL[: k + 1]
    _install_scores(monkeypatch, pool, {}, default=100)
    result = candidate.select_official_any_prize_1exchange(pool, k)
    assert result.seed.original_ranks == DONOR_SEEDS[k]
    assert result.ordered_candidate_pool == pool
    assert result.tickets == tuple(pool[rank - 1] for rank in DONOR_SEEDS[k])
    assert result.terminal == result.seed
    assert result.exchanges == ()
    assert result.completed_sweeps == 1
    assert not result.output_differs_from_min_overlap


def test_complete_best_improvement_sweeps_and_frozen_tie_break(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = POOL[:7][::-1]  # Original rank deliberately differs from ticket lexicographic order.
    initial = (1, 2, 3, 4, 5)
    first = (1, 2, 3, 4, 6)
    terminal = (1, 2, 3, 6, 7)
    scores = {
        initial: 100,
        (2, 3, 4, 5, 6): 110,  # Encountered earlier in the sweep; loses the rank-vector tie.
        (1, 2, 3, 4, 7): 110,
        first: 110,
        terminal: 120,
        (1, 2, 4, 6, 7): 120,  # A terminal plateau is never accepted.
    }
    monkeypatch.setattr(candidate, "_seed_original_ranks", _prefix_seed)
    calls = _install_scores(monkeypatch, pool, scores)
    result = candidate.select_official_any_prize_1exchange(pool, 5)
    assert tuple(state.original_ranks for state in result.states) == (initial, first, terminal)
    assert [(move.outgoing_slot, move.incoming_original_rank) for move in result.exchanges] == [
        (4, 6),
        (3, 7),
    ]
    assert all(
        move.resulting_outcome_count > move.previous_outcome_count for move in result.exchanges
    )
    assert result.neighbors_examined == 3 * 5 * 2
    assert result.completed_sweeps == 3
    assert result.exact_evaluations == len(calls) == len(set(calls))
    assert result.tickets == tuple(pool[rank - 1] for rank in terminal)
    assert result.terminal_local_optimum and result.output_differs_from_min_overlap
    assert all(
        scores.get(ranks, 90) <= 120
        for ranks in itertools.combinations(range(1, 8), 5)
        if len(set(ranks) ^ set(terminal)) == 2
    )
    assert candidate.select_official_any_prize_1exchange(pool, 5) == result


@pytest.mark.parametrize("k", (5, 10, 20))
def test_pool_equal_to_k_has_empty_neighborhood(monkeypatch: pytest.MonkeyPatch, k: int) -> None:
    pool = POOL[:k]
    calls = _install_scores(monkeypatch, pool, {}, default=100)
    result = candidate.select_official_any_prize_1exchange(pool, k)
    assert result.tickets == pool
    assert len(calls) == result.exact_evaluations == 1
    assert result.neighbors_examined == 0
    assert result.completed_sweeps == 1
    assert result.terminal_local_optimum


@pytest.mark.parametrize("k", (5, 10, 20))
def test_real_exact_b649_model_full_neighborhood_certificate(
    monkeypatch: pytest.MonkeyPatch, k: int
) -> None:
    """All possible portfolios in these K+1 pools are scored by the real evaluator."""
    pool = POOL[: k + 1]
    rank_by_ticket = {ticket: rank for rank, ticket in enumerate(pool, 1)}
    oracle: dict[Ranks, exact.ExactPortfolioProbability] = {}
    real_evaluate = exact.evaluate_portfolio

    def observe(
        portfolio: Sequence[Sequence[int]],
        *,
        pool_size: int,
        draw_size: int,
        outright_matches: int,
        draws: exact.DrawMasks,
    ) -> exact.ExactPortfolioProbability:
        assert (pool_size, draw_size, outright_matches, draws.size) == (49, 6, 3, 13983816)
        ranks = tuple(rank_by_ticket[tuple(ticket)] for ticket in portfolio)
        assert ranks not in oracle
        evaluated = real_evaluate(
            portfolio,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            draws=draws,
        )
        oracle[ranks] = evaluated
        return evaluated

    monkeypatch.setattr(exact, "evaluate_portfolio", observe)
    started = time.monotonic()
    result = candidate.select_official_any_prize_1exchange(pool, k)
    elapsed = time.monotonic() - started
    assert set(oracle) == set(itertools.combinations(range(1, k + 2), k))
    assert result.seed.original_ranks == DONOR_SEEDS[k]
    assert result.seed.probability == oracle[DONOR_SEEDS[k]]
    assert len(result.tickets) == len(set(result.tickets)) == k
    assert set(result.tickets) <= set(pool)
    assert result.ordered_candidate_pool == pool
    assert result.exact_evaluations == len(oracle) == k + 1
    assert result.completed_sweeps == len(result.exchanges) + 1
    assert result.neighbors_examined == result.completed_sweeps * k
    assert result.terminal.probability.official_any_prize_outcome_count == max(
        value.official_any_prize_outcome_count for value in oracle.values()
    )
    assert result.absolute_probability_delta >= 0
    for before, after in itertools.pairwise(result.states):
        assert len(set(before.original_ranks) ^ set(after.original_ranks)) == 2
        assert after.probability.official_any_prize_outcome_count > (
            before.probability.official_any_prize_outcome_count
        )
    assert result.terminal_local_optimum
    print(
        "STRUCTURAL_SYNTHETIC_B649 "
        + json.dumps(
            {
                "pool_size": len(pool),
                "k": k,
                "exact_evaluations": result.exact_evaluations,
                "accepted_moves": len(result.exchanges),
                "wall_seconds": elapsed,
                "seed_probability": str(result.seed.probability.official_any_prize),
                "terminal_probability": str(result.terminal.probability.official_any_prize),
                "absolute_delta": str(result.absolute_probability_delta),
                "seed_outcome_count": result.seed.probability.official_any_prize_outcome_count,
                "terminal_outcome_count": (
                    result.terminal.probability.official_any_prize_outcome_count
                ),
                "terminal_local_optimum": result.terminal_local_optimum,
                "output_differs_from_min_overlap": result.output_differs_from_min_overlap,
            },
            sort_keys=True,
        )
    )


@pytest.mark.parametrize(
    "bad_pool",
    [
        (),
        POOL[:4],
        (POOL[0],) * 6,
        (*POOL[:5], (1, 2, 3, 4, 5)),
        (*POOL[:5], (1, 2, 3, 4, 5, 5)),
        (*POOL[:5], (0, 2, 3, 4, 5, 6)),
        (*POOL[:5], (1, 2, 3, 4, 5, 50)),
        (*POOL[:5], (True, 2, 3, 4, 5, 6)),
        (*POOL[:5], (1.0, 2, 3, 4, 5, 6)),
        {"tickets": POOL},
        set(POOL),
        (*POOL[:5], {1, 2, 3, 4, 5, 6}),
        "123456",
    ],
)
def test_invalid_pool_is_rejected_without_authority_or_evaluation(bad_pool: object) -> None:
    with pytest.raises(ValueError):
        candidate.select_official_any_prize_1exchange(
            cast(Sequence[Sequence[int]], bad_pool),
            5,
            seed_authority_repository=Path("/nonexistent-seed-authority"),
        )


@pytest.mark.parametrize("k", (-1, 0, 2, 3, 6, 21, True, 5.0))
def test_unsupported_budget_rejected(k: object) -> None:
    with pytest.raises(ValueError, match="k must"):
        candidate.select_official_any_prize_1exchange(POOL, cast(int, k))


@pytest.mark.parametrize("field", ("history", "outcomes", "winning_numbers", "scores", "draws"))
def test_outcome_or_alternate_scoring_arguments_are_not_accepted(field: str) -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        candidate.select_official_any_prize_1exchange(POOL, 5, **{field: None})


def test_input_unchanged_and_no_rng_or_outcome_properties_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OutcomeTrap(list[list[int]]):
        @property
        def outcomes(self) -> object:
            raise AssertionError("outcome access")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("RNG access")

    for name in ("random", "seed", "sample", "shuffle", "randint", "choice"):
        monkeypatch.setattr(random, name, forbidden)
    monkeypatch.setattr(np.random, "default_rng", forbidden)
    pool = POOL[:6][::-1]
    raw = OutcomeTrap([list(reversed(ticket)) for ticket in pool])
    snapshot = [row[:] for row in raw]
    _install_scores(monkeypatch, pool, {}, default=100)
    result = candidate.select_official_any_prize_1exchange(raw, 5)
    assert raw == snapshot
    assert result.ordered_candidate_pool == pool
    assert result == candidate.select_official_any_prize_1exchange(raw, 5)


def test_missing_locator_fails_without_fallback() -> None:
    with pytest.raises(candidate.SeedAuthorityUnavailable, match="LOCATOR_UNAVAILABLE"):
        candidate.select_official_any_prize_1exchange(
            POOL[:6], 5, seed_authority_repository=Path("/nonexistent-seed-authority")
        )


def test_wrong_blob_bytes_rejected_before_compiling(monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong_blob(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, stdout=b"raise AssertionError('executed')")

    monkeypatch.setattr(subprocess, "run", wrong_blob)
    with pytest.raises(candidate.SeedAuthorityUnavailable, match="CONTENT_MISMATCH"):
        candidate.select_official_any_prize_1exchange(
            POOL[:6], 5, seed_authority_repository=Path("/different-locator-with-wrong-bytes")
        )


def test_frozen_identity_and_no_production_module_imports() -> None:
    assert candidate.METHOD_ID == "B649_CANDIDATE_SET_OFFICIAL_ANY_PRIZE_1EXCHANGE"
    assert candidate.METHOD_VERSION == candidate.SEED_METHOD_VERSION == "1.0.0"
    assert candidate.SEED_METHOD_ID == "B649_DETERMINISTIC_MIN_OVERLAP"
    assert candidate.SEED_AUTHORITY_BLOB == "4178aaf1322e81f5249914312c7582a5ae76aae0"
    tree = ast.parse(inspect.getsource(candidate))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        module and module.startswith(("lottolab.application", "lottolab.infrastructure", "random"))
        for module in imports
    )
