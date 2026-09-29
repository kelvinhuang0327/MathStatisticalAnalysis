"""Structural oracles for the frozen direct exact-coverage selector.

No historical outcome, database or RNG is used. The small-lottery oracle
enumerates every (main draw, special) outcome and applies the win rule
``|ticket & (draw | {special})| >= outright_matches``. That rule is equivalent to
the official one (an outright win, or one match short with the special in the
ticket) but shares no code with the evaluator's analytic special collapse or
with the selector's incremental engine. ``reference_search`` is an independent
re-implementation of the written contract on top of that oracle.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import itertools
import json
import math
import socket
import sqlite3
from collections.abc import Sequence
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_direct_exact_coverage_selector as candidate
from lottolab.research import b649_official_any_prize_exact as exact

type Ticket = tuple[int, ...]
type Pool = tuple[Ticket, ...]

MODULE_PATH = Path(candidate.__file__)
SMALL_SPACES = (
    candidate.DrawSpace(11, 4, 3),
    candidate.DrawSpace(10, 4, 2),
    candidate.DrawSpace(9, 3, 2),
)


def arithmetic_pool(count: int, multiplier: int, offset: int, span: int, draw_size: int) -> Pool:
    """Synthetic ranked pool with at most ``span`` distinct tickets (wide numbers only)."""

    pool: list[Ticket] = []
    index = 0
    while len(pool) < count:
        assert index < 100_000, "fixture cannot be filled"
        ticket = tuple(
            sorted(1 + (multiplier * index + j * j + offset * j) % span for j in range(draw_size))
        )
        index += 1
        if len(set(ticket)) == draw_size and ticket not in pool:
            pool.append(ticket)
    return tuple(pool)


def scrambled_pool(count: int, multiplier: int, offset: int, span: int, draw_size: int) -> Pool:
    """First ``count`` tickets over ``1..span`` under a fixed arithmetic scramble."""

    def key(ticket: Ticket) -> tuple[int, Ticket]:
        weight = sum(w * n * n for w, n in enumerate(ticket, 1))
        return (weight * multiplier + offset) % 997, ticket

    combos = itertools.combinations(range(1, span + 1), draw_size)
    return tuple(sorted(combos, key=key)[:count])


def synthetic_pool(count: int, multiplier: int, offset: int, span: int, draw_size: int) -> Pool:
    make = arithmetic_pool if span >= exact.BIG_LOTTO_POOL_SIZE else scrambled_pool
    return make(count, multiplier, offset, span, draw_size)


def outcome_masks(space: candidate.DrawSpace) -> tuple[int, ...]:
    """One mask ``draw | {special}`` for every (main draw, special) outcome."""

    masks: list[int] = []
    for draw in itertools.combinations(range(space.pool_size), space.draw_size):
        draw_mask = sum(1 << number for number in draw)
        masks.extend(
            draw_mask | (1 << special)
            for special in range(space.pool_size)
            if not draw_mask >> special & 1
        )
    return tuple(masks)


def brute_count(portfolio: Sequence[Ticket], space: candidate.DrawSpace) -> int:
    ticket_masks = [sum(1 << (number - 1) for number in ticket) for ticket in portfolio]
    return sum(
        any((mask & outcome).bit_count() >= space.outright_matches for mask in ticket_masks)
        for outcome in outcome_masks(space)
    )


def reference_search(
    pool: Pool, k: int, space: candidate.DrawSpace, max_swaps: int
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int, bool]:
    """Independent statement of the contract: (pick order, greedy, final, swaps, certified)."""

    @cache
    def count(ranks: tuple[int, ...]) -> int:
        return brute_count([pool[rank - 1] for rank in ranks], space)

    picked: list[int] = []
    for _ in range(k):
        options = [rank for rank in range(1, len(pool) + 1) if rank not in picked]
        scored = [(count(tuple(sorted((*picked, rank)))), rank) for rank in options]
        best = max(score for score, _ in scored)
        picked.append(min(rank for score, rank in scored if score == best))
    greedy = tuple(sorted(picked))
    current = greedy
    swaps = 0
    while swaps < max_swaps:
        best_move: tuple[int, tuple[int, ...]] | None = None
        for outgoing in current:
            for incoming in range(1, len(pool) + 1):
                if incoming in current:
                    continue
                ranks = tuple(sorted((*(r for r in current if r != outgoing), incoming)))
                if count(ranks) <= count(current):
                    continue
                key = (-count(ranks), ranks)
                if best_move is None or key < best_move:
                    best_move = key
        if best_move is None:
            return tuple(picked), greedy, current, swaps, True
        current = best_move[1]
        swaps += 1
    return tuple(picked), greedy, current, swaps, False


# (space, pool size, k, (multiplier, offset, span), swap bound); the first four reach Stage B.
SMALL_CASES = (
    (SMALL_SPACES[0], 14, 4, (3, 1, 11), 2),  # two swaps, bound hit, not certified
    (SMALL_SPACES[0], 14, 4, (7, 1, 11), 2),  # one swap, then certified
    (SMALL_SPACES[0], 12, 5, (5, 1, 11), 2),  # two swaps, bound hit, not certified
    (SMALL_SPACES[2], 14, 4, (13, 1, 9), 2),  # outright_matches == 2, one swap, certified
    (SMALL_SPACES[0], 13, 3, (7, 4, 11), 2),
    (SMALL_SPACES[0], 12, 4, (13, 4, 11), 1),  # bound of one swap
    (SMALL_SPACES[1], 12, 3, (9, 1, 10), 1),
    (SMALL_SPACES[1], 12, 4, (13, 2, 10), 3),
    (SMALL_SPACES[2], 11, 5, (3, 4, 9), 2),
)


@pytest.mark.parametrize(("space", "size", "k", "shape", "max_swaps"), SMALL_CASES)
def test_search_matches_independent_reference_on_small_lotteries(
    space: candidate.DrawSpace,
    size: int,
    k: int,
    shape: tuple[int, int, int],
    max_swaps: int,
) -> None:
    pool = synthetic_pool(size, shape[0], shape[1], shape[2], space.draw_size)
    result = candidate.run_direct_exact_coverage_search(
        pool, k, space=space, max_accepted_swaps=max_swaps
    )
    pick_order, greedy, final, swaps, certified = reference_search(pool, k, space, max_swaps)
    assert result.greedy_pick_order == pick_order
    assert result.greedy_ranks == greedy
    assert result.final_ranks == final
    assert len(result.swaps) == swaps
    assert result.local_optimum_certified is certified

    # Exact evaluator agreement: the brute-force oracle, not the selector's engine.
    tickets = [pool[rank - 1] for rank in pick_order]
    running = [brute_count(tickets[: step + 1], space) for step in range(k)]
    assert result.greedy_marginal_gains == tuple(
        after - before for before, after in zip((0, *running), running, strict=False)
    )
    assert result.greedy_probability.official_any_prize_outcome_count == running[-1]
    assert result.final_probability.official_any_prize_outcome_count == brute_count(
        result.tickets, space
    )
    assert result == candidate.run_direct_exact_coverage_search(
        pool, k, space=space, max_accepted_swaps=max_swaps
    )


def test_swaps_only_ever_improve_the_greedy_initialisation() -> None:
    bound_hit = certified_after_swap = 0
    for space, size, k, shape, max_swaps in SMALL_CASES[:4]:
        pool = synthetic_pool(size, *shape, space.draw_size)
        result = candidate.run_direct_exact_coverage_search(
            pool, k, space=space, max_accepted_swaps=max_swaps
        )
        assert 1 <= len(result.swaps) <= max_swaps
        counts = [result.greedy_probability.official_any_prize_outcome_count]
        counts += [swap.resulting_outcome_count for swap in result.swaps]
        assert counts == sorted(set(counts)), "every accepted swap is a strict improvement"
        assert result.final_probability.official_any_prize_outcome_count == counts[-1]
        assert result.absolute_probability_delta > 0
        assert len(set(result.final_ranks)) == k
        bound_hit += not result.local_optimum_certified
        certified_after_swap += result.local_optimum_certified

        greedy_only = candidate.run_direct_exact_coverage_search(
            pool, k, space=space, max_accepted_swaps=0
        )
        assert greedy_only.swaps == ()
        assert greedy_only.final_ranks == greedy_only.greedy_ranks == result.greedy_ranks
        assert not greedy_only.local_optimum_certified
    assert bound_hit >= 1
    assert certified_after_swap >= 1


def test_first_pick_is_first_pool_position_and_ties_follow_pool_order() -> None:
    space = SMALL_SPACES[0]
    anchor: Ticket = (1, 2, 3, 4)
    mirror_a: Ticket = (5, 6, 7, 8)
    mirror_b: Ticket = (5, 9, 10, 11)  # image of mirror_a under a relabelling fixing the anchor
    forward = candidate.run_direct_exact_coverage_search(
        (anchor, mirror_a, mirror_b), 2, space=space, max_accepted_swaps=0
    )
    backward = candidate.run_direct_exact_coverage_search(
        (anchor, mirror_b, mirror_a), 2, space=space, max_accepted_swaps=0
    )
    assert forward.greedy_marginal_gains[1] == backward.greedy_marginal_gains[1]
    assert forward.greedy_pick_order == (1, 2)
    assert backward.greedy_pick_order == (1, 2)
    assert forward.tickets == (anchor, mirror_a)
    assert backward.tickets == (anchor, mirror_b)

    # The single-ticket count is ticket independent, so every first pick ties.
    reversed_pool = tuple(reversed(synthetic_pool(9, 11, 3, 11, 4)))
    result = candidate.run_direct_exact_coverage_search(reversed_pool, 3, space=space)
    assert result.greedy_pick_order[0] == 1


def test_gains_and_argmax_agree_with_canonical_evaluator_at_full_scale() -> None:
    pool = synthetic_pool(6, 11, 3, 49, 6)
    result = candidate.run_direct_exact_coverage_search(pool, 3, max_accepted_swaps=0)
    draws = exact.all_main_draw_masks(49, 6)

    def count(ranks: Sequence[int]) -> int:
        return exact.evaluate_portfolio(
            [pool[rank - 1] for rank in ranks], draws=draws
        ).official_any_prize_outcome_count

    picked: list[int] = []
    for step, gain in enumerate(result.greedy_marginal_gains):
        base = count(picked) if picked else 0
        options = {
            rank: count((*picked, rank)) - base
            for rank in range(1, len(pool) + 1)
            if rank not in picked
        }
        assert gain == max(options.values())
        assert result.greedy_pick_order[step] == min(
            rank for rank, value in options.items() if value == gain
        )
        picked.append(result.greedy_pick_order[step])
    assert result.final_probability == exact.evaluate_portfolio(result.tickets, draws=draws)


def test_frozen_entry_rejects_unsupported_budgets_and_illegal_pools() -> None:
    pool = synthetic_pool(21, 11, 3, 49, 6)
    for bad_k in (0, 5, 9, 11, 15, 21, True):
        with pytest.raises(ValueError):
            candidate.select_direct_exact_coverage(pool, bad_k)
    with pytest.raises(ValueError, match="at least k"):
        candidate.select_direct_exact_coverage(pool[:9], 10)
    with pytest.raises(ValueError, match="distinct"):
        candidate.select_direct_exact_coverage((*pool[:9], pool[0], pool[0]), 10)
    for bad_ticket in (
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 6, 7),
        (1, 2, 3, 4, 5, 50),
        (0, 1, 2, 3, 4, 5),
    ):
        with pytest.raises(ValueError):
            candidate.select_direct_exact_coverage((*pool[:9], bad_ticket, pool[10]), 10)
    with pytest.raises(ValueError, match="distinct"):
        candidate.select_direct_exact_coverage((*pool[:9], (1, 1, 2, 3, 4, 5), pool[10]), 10)
    with pytest.raises(ValueError):
        candidate.select_direct_exact_coverage((*pool[:9], (1, 2, 3, 4, 5, True), pool[10]), 10)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        candidate.select_direct_exact_coverage("not a pool", 10)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        candidate.run_direct_exact_coverage_search(pool, 10, max_accepted_swaps=-1)


def test_selector_is_outcome_blind() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(f"{node.module}.*" if node.level == 0 else "relative")
    assert imported <= {
        "__future__.*",
        "collections.abc.*",
        "dataclasses.*",
        "fractions.*",
        "typing.*",
        "numpy",
        "numpy.typing",
        "lottolab.research.*",
    }
    assert {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "lottolab.research"
        for alias in node.names
    } == {"b649_official_any_prize_exact"}
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & {"open", "eval", "exec", "compile", "__import__", "input"}
    assert list(inspect.signature(candidate.select_direct_exact_coverage).parameters) == [
        "ordered_candidate_pool",
        "k",
    ]
    assert not {"draw", "history", "outcome", "result", "seed", "rng"} & {
        name.lower()
        for name in inspect.signature(candidate.run_direct_exact_coverage_search).parameters
    }


def test_search_touches_no_file_database_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the selector must not read files, databases or the network")

    pool = synthetic_pool(12, 11, 3, 11, 4)
    expected = candidate.run_direct_exact_coverage_search(pool, 4, space=SMALL_SPACES[0])
    with monkeypatch.context() as patched:
        patched.setattr(builtins, "open", forbidden)
        patched.setattr(sqlite3, "connect", forbidden)
        patched.setattr(socket.socket, "connect", forbidden)
        assert (
            candidate.run_direct_exact_coverage_search(pool, 4, space=SMALL_SPACES[0]) == expected
        )


def test_canonical_evaluator_gate_fails_closed_on_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = exact.evaluate_portfolio

    def off_by_one(
        portfolio: Sequence[Sequence[int]], **kwargs: Any
    ) -> exact.ExactPortfolioProbability:
        truth = real(portfolio, **kwargs)
        return exact.ExactPortfolioProbability(
            truth.main_draw_count,
            truth.special_count,
            truth.m3_plus_draw_count,
            truth.official_any_prize_outcome_count + 1,
        )

    pool = synthetic_pool(12, 11, 3, 11, 4)
    monkeypatch.setattr(exact, "evaluate_portfolio", off_by_one)
    with pytest.raises(AssertionError, match="incremental coverage engine disagrees"):
        candidate.run_direct_exact_coverage_search(pool, 4, space=SMALL_SPACES[0])


ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/matrix-native-results"
    / "b649-direct-exact-success-coverage-selector-r1-freeze.json"
)


def load_artifact() -> dict[str, Any]:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def fixture_pool(spec: dict[str, Any]) -> Pool:
    make = {"ARITHMETIC_V1": arithmetic_pool, "SCRAMBLED_COMBINATIONS_V1": scrambled_pool}[
        spec["GENERATOR"]
    ]
    return make(spec["COUNT"], spec["MULTIPLIER"], spec["OFFSET"], spec["SPAN"], 6)


def min_overlap_reference(pool: Pool, k: int) -> tuple[int, ...]:
    """The pinned MIN_OVERLAP rule as its docstring states it (checks recorded ranks)."""

    def overlap(first: int, second: int) -> int:
        return len(set(pool[first]) & set(pool[second]))

    chosen = [0]
    remaining = set(range(1, len(pool)))
    while len(chosen) < k:
        best = min(
            remaining,
            key=lambda index: (
                max(overlap(index, member) for member in chosen),
                sum(overlap(index, member) for member in chosen),
                index,
            ),
        )
        chosen.append(best)
        remaining.remove(best)
    return tuple(sorted(index + 1 for index in chosen))


def test_freeze_artifact_binds_the_exact_modules_and_declares_no_outcome_access() -> None:
    artifact = load_artifact()
    assert artifact["MODULE_SHA256"] == hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest()
    authority = artifact["EXACT_OBJECTIVE_AUTHORITY"]
    assert (
        authority["MODULE_SHA256"] == hashlib.sha256(Path(exact.__file__).read_bytes()).hexdigest()
    )
    assert authority["SECOND_SUCCESS_METRIC_CREATED"] is False
    assert authority["TOTAL_OUTCOMES"] == math.comb(49, 6) * 43
    assert (artifact["METHOD_ID"], artifact["METHOD_VERSION"]) == (
        candidate.METHOD_ID,
        candidate.METHOD_VERSION,
    )
    assert artifact["CANDIDATE_ID"] == candidate.CANDIDATE_ID
    assert (artifact["PRIMARY_K"], artifact["SECONDARY_K"]) == (10, 20)
    assert artifact["SUPPORTED_K"] == list(candidate.SUPPORTED_K)
    assert artifact["ALGORITHM_CONTRACT"]["MAX_ACCEPTED_SWAPS"] == candidate.MAX_ACCEPTED_SWAPS
    assert artifact["DETERMINISTIC_TIEBREAK"]["STAGE_B"] == candidate.SWAP_TIE_BREAK
    assert artifact["DETERMINISTIC_TIEBREAK"]["STAGE_A"].startswith(candidate.GREEDY_TIE_BREAK)
    assert artifact["OUTCOME_DATA_ACCESSED"] == "NO"
    assert artifact["OOS_REPLAY"] == "NOT RUN"
    assert artifact["PREDICTIVE_LIFT_CLAIMED"] == "NO"


def test_recorded_fixtures_recount_exactly_and_are_internally_consistent() -> None:
    artifact = load_artifact()
    draws = exact.all_main_draw_masks(49, 6)
    total = math.comb(49, 6) * 43
    budgets: set[int] = set()
    for fixture in artifact["FIXTURES"]:
        k = fixture["K"]
        budgets.add(k)
        spec = fixture["POOL"]
        pool = fixture_pool(spec)
        assert len(pool) == spec["COUNT"]
        assert len(set(pool)) == len(pool)
        pool_json = json.dumps([list(ticket) for ticket in pool], separators=(",", ":"))
        assert hashlib.sha256(pool_json.encode()).hexdigest() == spec["SHA256"]

        blocks = {
            name: fixture[name]
            for name in (
                "OPERATIONAL_INCUMBENT_PREFIX",
                "MIN_OVERLAP",
                "SELECTOR_GREEDY",
                "SELECTOR_FINAL",
            )
        }
        for name, block in blocks.items():
            ranks: list[int] = block["RANKS"]
            assert ranks == sorted(set(ranks)), name
            assert len(ranks) == k, name
            assert all(1 <= rank <= len(pool) for rank in ranks), name
            tickets: list[Ticket] = [pool[rank - 1] for rank in ranks]
            assert all(
                len(ticket) == 6
                and len(set(ticket)) == 6
                and all(1 <= number <= 49 for number in ticket)
                for ticket in tickets
            )
            probability = exact.evaluate_portfolio(tickets, draws=draws)
            assert block["OUTCOME_COUNT"] == probability.official_any_prize_outcome_count, name
            assert block["M3_PLUS_DRAW_COUNT"] == probability.m3_plus_draw_count, name
            assert block["PROBABILITY_FRACTION"] == str(Fraction(block["OUTCOME_COUNT"], total))

        assert blocks["OPERATIONAL_INCUMBENT_PREFIX"]["RANKS"] == list(range(1, k + 1))
        assert blocks["MIN_OVERLAP"]["RANKS"] == list(min_overlap_reference(pool, k))
        greedy, final = blocks["SELECTOR_GREEDY"], blocks["SELECTOR_FINAL"]
        assert final["OUTCOME_COUNT"] >= greedy["OUTCOME_COUNT"]
        assert sum(fixture["GREEDY_MARGINAL_GAINS"]) == greedy["OUTCOME_COUNT"]
        assert sorted(fixture["GREEDY_PICK_ORDER"]) == greedy["RANKS"]
        assert fixture["GREEDY_PICK_ORDER"][0] == 1
        assert len(fixture["ACCEPTED_SWAPS"]) <= candidate.MAX_ACCEPTED_SWAPS

        current, count = set(greedy["RANKS"]), greedy["OUTCOME_COUNT"]
        for swap in fixture["ACCEPTED_SWAPS"]:
            assert swap["OUTGOING_RANK"] in current
            assert swap["INCOMING_RANK"] not in current
            current = (current - {swap["OUTGOING_RANK"]}) | {swap["INCOMING_RANK"]}
            assert swap["RESULTING_RANKS"] == sorted(current)
            assert swap["PREVIOUS_OUTCOME_COUNT"] == count
            assert swap["RESULTING_OUTCOME_COUNT"] > count
            count = swap["RESULTING_OUTCOME_COUNT"]
        assert sorted(current) == final["RANKS"]
        assert count == final["OUTCOME_COUNT"]
        assert fixture["LOCAL_OPTIMUM_CERTIFIED"] == (
            len(fixture["ACCEPTED_SWAPS"]) < candidate.MAX_ACCEPTED_SWAPS
        )

        for key, baseline in (
            ("DECISION_LEVERAGE_VS_INCUMBENT", "OPERATIONAL_INCUMBENT_PREFIX"),
            ("DECISION_LEVERAGE_VS_MIN_OVERLAP", "MIN_OVERLAP"),
        ):
            leverage, base = fixture[key], blocks[baseline]
            assert leverage["TICKETS_CHANGED"] == k - len(set(final["RANKS"]) & set(base["RANKS"]))
            assert leverage["SELECTOR_PORTFOLIO_IDENTICAL"] == (final["RANKS"] == base["RANKS"])
            assert leverage["DELTA_OUTCOME_COUNT"] == final["OUTCOME_COUNT"] - base["OUTCOME_COUNT"]
    assert budgets == {10, 20}


def test_frozen_k10_entry_reproduces_the_recorded_fixture() -> None:
    fixture = next(f for f in load_artifact()["FIXTURES"] if f["FIXTURE_ID"] == "F0_SPREAD_P12_K10")
    pool = fixture_pool(fixture["POOL"])
    result = candidate.select_direct_exact_coverage(pool, fixture["K"])
    assert list(result.greedy_pick_order) == fixture["GREEDY_PICK_ORDER"]
    assert list(result.greedy_marginal_gains) == fixture["GREEDY_MARGINAL_GAINS"]
    assert list(result.greedy_ranks) == fixture["SELECTOR_GREEDY"]["RANKS"]
    assert list(result.final_ranks) == fixture["SELECTOR_FINAL"]["RANKS"]
    assert [swap.resulting_outcome_count for swap in result.swaps] == [
        swap["RESULTING_OUTCOME_COUNT"] for swap in fixture["ACCEPTED_SWAPS"]
    ]
    assert result.local_optimum_certified is fixture["LOCAL_OPTIMUM_CERTIFIED"]
    assert (
        result.final_probability.official_any_prize_outcome_count
        == (fixture["SELECTOR_FINAL"]["OUTCOME_COUNT"])
    )
    assert (
        result.greedy_probability.official_any_prize_outcome_count
        <= result.final_probability.official_any_prize_outcome_count
    )
    assert len(result.tickets) == fixture["K"] == len(set(result.tickets))
    assert set(result.tickets) <= set(pool)
    assert result.canonical_evaluations == fixture["CANONICAL_EVALUATIONS"]
    assert result.candidate_gain_evaluations == fixture["CANDIDATE_GAIN_EVALUATIONS"]
