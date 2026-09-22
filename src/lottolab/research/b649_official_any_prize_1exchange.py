"""Frozen B649 exact official-any-prize refinement of an ordered candidate pool.

Only strict best-improvement ticket exchanges are accepted. Equal best moves
use (resulting ascending original-rank vector, outgoing slot, incoming rank).
Ranks are one-based; slots are zero-based in the current rank-ordered portfolio.
Every sweep is complete, including the final sweep certifying a 1-exchange
local optimum. There is no claim of a global optimum or predictive advantage.

MIN_OVERLAP is reused through an immutable Git-blob locator, not an application
import or a copied algorithm. Only its original selection function and two pure
helpers are compiled. The two boundary adapters supply the *already ordered*
pool and capture its selected indices; they do not reconstruct, sort or score
the pool. The caller may point the locator at another repository containing the
same pinned blob. Missing or changed authority fails explicitly, with no fallback.

This module reads only that pinned source blob. It accepts no draws, history,
empirical scores, alternate objectives, sample spaces or stochastic controls.
Exact scoring reuses b649_official_any_prize_exact over the entire B649 space.
"""

from __future__ import annotations
import __future__

import ast
import hashlib
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Final, Protocol, cast

import numpy as np

from lottolab.research import b649_official_any_prize_exact as exact

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type RankVector = tuple[int, ...]
type MoveKey = tuple[int, RankVector, int, int]

CANDIDATE_ID: Final = "B649_CANDIDATE_SET_OFFICIAL_ANY_PRIZE_1EXCHANGE_V1"
METHOD_ID: Final = "B649_CANDIDATE_SET_OFFICIAL_ANY_PRIZE_1EXCHANGE"
METHOD_VERSION: Final = "1.0.0"
LOTTERY: Final = "BIG_LOTTO"
SUPPORTED_K: Final = (5, 10, 20)
PRIMARY_OBJECTIVE: Final = "OFFICIAL_ANY_PRIZE_EXACT"
SEED_METHOD_ID: Final = "B649_DETERMINISTIC_MIN_OVERLAP"
SEED_METHOD_VERSION: Final = "1.0.0"
# Provenance only: neither the source checkout nor this file path is a dependency.
SEED_AUTHORITY_COMMIT: Final = "fbed3da52e4b6b8907afe71eed52e802b51a5cb0"
SEED_AUTHORITY_PATH: Final = "src/lottolab/application/b649_k_dpp_portfolio_selector.py"
SEED_AUTHORITY_BLOB: Final = "4178aaf1322e81f5249914312c7582a5ae76aae0"
SEED_AUTHORITY_SHA256: Final = "fb96b7f481d08dbea55b6dee42143fed5fa7cfe63055e1b581e92f3befb82576"
_SEED_FUNCTIONS: Final = frozenset(
    {"select_deterministic_min_overlap", "_overlap_counts", "_require_allowed_k"}
)
_SEED_CONSTANTS: Final = frozenset({"ALLOWED_K", "MIN_NUMBER", "MAX_NUMBER"})


class SeedAuthorityUnavailable(RuntimeError):
    """The pinned MIN_OVERLAP source cannot be resolved or verified."""


@dataclass(frozen=True, slots=True)
class _SeedEntry:
    ticket: Ticket


@dataclass(frozen=True, slots=True)
class _SeedPool:
    entries: tuple[_SeedEntry, ...]

    @property
    def candidate_count(self) -> int:
        return len(self.entries)


class _SeedSelector(Protocol):
    def __call__(self, candidates: _SeedPool, *, source: None, k: int) -> tuple[int, ...]: ...


def _already_ordered_pool(pool: _SeedPool) -> _SeedPool:
    return pool


def _capture_seed_indices(
    _arm: str,
    _pool: _SeedPool,
    _source: None,
    k: int,
    *,
    seed: None,
    status: str,
    sampling_order: tuple[int, ...],
    portfolio_order: tuple[int, ...] = (),
) -> tuple[int, ...]:
    if status != "FEASIBLE" or seed is not None or len(portfolio_order) != k:
        raise SeedAuthorityUnavailable("MIN_OVERLAP did not return a feasible fixed-K seed")
    return portfolio_order


@lru_cache(maxsize=4)
def _load_seed_selector(repository: Path) -> _SeedSelector:
    """Bind the original pure functions from verified immutable authority bytes."""
    try:
        source = subprocess.run(
            ["git", "-C", str(repository), "cat-file", "blob", SEED_AUTHORITY_BLOB],
            check=True,
            capture_output=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise SeedAuthorityUnavailable(
            f"MIN_OVERLAP_AUTHORITY_LOCATOR_UNAVAILABLE: {repository} / {SEED_AUTHORITY_BLOB}"
        ) from exc
    if hashlib.sha256(source).hexdigest() != SEED_AUTHORITY_SHA256:
        raise SeedAuthorityUnavailable("MIN_OVERLAP_AUTHORITY_CONTENT_MISMATCH")

    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in _SEED_FUNCTIONS
    ]
    constants = {
        node.target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in _SEED_CONSTANTS
        and node.value is not None
    }
    if (
        frozenset(node.name for node in functions) != _SEED_FUNCTIONS
        or frozenset(constants) != _SEED_CONSTANTS
    ):
        raise SeedAuthorityUnavailable("MIN_OVERLAP_AUTHORITY_SYMBOL_MISMATCH")
    namespace: dict[str, object] = {
        **constants,
        "np": np,
        "build_kdpp_candidate_pool": _already_ordered_pool,
        "_selection": _capture_seed_indices,
    }
    # No imports, other arms, source-identity readers or module-level execution.
    code = compile(
        ast.Module(body=cast(list[ast.stmt], functions), type_ignores=[]),
        f"git-blob:{SEED_AUTHORITY_BLOB}",
        "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    exec(code, namespace)
    return cast(_SeedSelector, namespace["select_deterministic_min_overlap"])


def _seed_original_ranks(pool: Portfolio, k: int, repository: Path) -> RankVector:
    selector = _load_seed_selector(repository)
    indices = selector(_SeedPool(tuple(_SeedEntry(ticket) for ticket in pool)), source=None, k=k)
    if (
        len(indices) != k
        or indices != tuple(sorted(set(indices)))
        or any(type(index) is not int or not 0 <= index < len(pool) for index in indices)
    ):
        raise SeedAuthorityUnavailable("MIN_OVERLAP returned invalid ordered pool indices")
    return tuple(index + 1 for index in indices)


def _validated_pool(ordered_candidate_pool: object, k: int) -> Portfolio:
    if type(k) is not int or k not in SUPPORTED_K:
        raise ValueError("k must be one of 5, 10, 20")
    if not isinstance(ordered_candidate_pool, Sequence) or isinstance(
        ordered_candidate_pool, (str, bytes)
    ):
        raise ValueError("candidate pool must be an ordered sequence of tickets")
    pool: list[Ticket] = []
    for raw in cast(Sequence[object], ordered_candidate_pool):
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("each candidate must be a sequence of six integers")
        numbers = cast(Sequence[object], raw)
        if len(numbers) != 6 or any(
            type(number) is not int or not 1 <= number <= 49 for number in numbers
        ):
            raise ValueError("each candidate must contain six integers in 1..49")
        ticket = tuple(sorted(cast(Sequence[int], numbers)))
        if len(set(ticket)) != 6:
            raise ValueError("candidate numbers must be distinct")
        pool.append(ticket)
    if len(set(pool)) != len(pool):
        raise ValueError("candidate tickets must be distinct; the pool is never deduplicated")
    if len(pool) < k:
        raise ValueError("candidate pool must contain at least k distinct tickets")
    return tuple(pool)


@dataclass(frozen=True, slots=True)
class SelectionState:
    original_ranks: RankVector
    probability: exact.ExactPortfolioProbability


@dataclass(frozen=True, slots=True)
class AcceptedExchange:
    outgoing_slot: int
    incoming_original_rank: int
    resulting_original_ranks: RankVector
    previous_outcome_count: int
    resulting_outcome_count: int


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    ordered_candidate_pool: Portfolio
    k: int
    states: tuple[SelectionState, ...]
    exchanges: tuple[AcceptedExchange, ...]
    exact_evaluations: int
    completed_sweeps: int
    neighbors_examined: int

    @property
    def seed(self) -> SelectionState:
        return self.states[0]

    @property
    def terminal(self) -> SelectionState:
        return self.states[-1]

    @property
    def tickets(self) -> Portfolio:
        return tuple(self.ordered_candidate_pool[rank - 1] for rank in self.terminal.original_ranks)

    @property
    def absolute_probability_delta(self) -> Fraction:
        return (
            self.terminal.probability.official_any_prize - self.seed.probability.official_any_prize
        )

    @property
    def terminal_local_optimum(self) -> bool:
        # Results are returned only after an entire sweep finds no strict improvement.
        return True

    @property
    def output_differs_from_min_overlap(self) -> bool:
        return self.terminal.original_ranks != self.seed.original_ranks


def select_official_any_prize_1exchange(
    ordered_candidate_pool: Sequence[Sequence[int]],
    k: int,
    *,
    seed_authority_repository: Path | None = None,
) -> CandidateSelection:
    """Reach a strict 1-exchange local optimum, reusing the exact frozen seed.

    The optional repository is only a locator for the fixed authority blob;
    changing its location cannot change the algorithm. It defaults to this
    source's repository. Numbers within each ticket are normalized; candidate
    order is never changed. Invalid or duplicate tickets fail rather than
    silently modifying the pool. No partial result or sweep limit is offered.
    """
    pool = _validated_pool(ordered_candidate_pool, k)
    repository = seed_authority_repository or Path(__file__).resolve().parents[3]
    seed_ranks = _seed_original_ranks(pool, k, repository.resolve())
    draws = exact.all_main_draw_masks(exact.BIG_LOTTO_POOL_SIZE, exact.BIG_LOTTO_DRAW_SIZE)
    evaluations: dict[RankVector, exact.ExactPortfolioProbability] = {}

    def evaluate(ranks: RankVector) -> exact.ExactPortfolioProbability:
        if ranks not in evaluations:
            evaluations[ranks] = exact.evaluate_portfolio(
                tuple(pool[rank - 1] for rank in ranks),
                pool_size=exact.BIG_LOTTO_POOL_SIZE,
                draw_size=exact.BIG_LOTTO_DRAW_SIZE,
                outright_matches=exact.BIG_LOTTO_OUTRIGHT_MATCHES,
                draws=draws,
            )
        return evaluations[ranks]

    states = [SelectionState(seed_ranks, evaluate(seed_ranks))]
    exchanges: list[AcceptedExchange] = []
    sweeps = 0
    neighbors_examined = 0
    while True:
        current = states[-1]
        current_count = current.probability.official_any_prize_outcome_count
        selected = set(current.original_ranks)
        best: MoveKey | None = None
        for outgoing_slot in range(k):
            for incoming_rank in range(1, len(pool) + 1):
                if incoming_rank in selected:
                    continue
                ranks = tuple(
                    sorted(
                        (
                            *current.original_ranks[:outgoing_slot],
                            *current.original_ranks[outgoing_slot + 1 :],
                            incoming_rank,
                        )
                    )
                )
                count = evaluate(ranks).official_any_prize_outcome_count
                neighbors_examined += 1
                if count <= current_count:
                    continue
                key = (-count, ranks, outgoing_slot, incoming_rank)
                if best is None or key < best:
                    best = key
        sweeps += 1
        if best is None:
            return CandidateSelection(
                pool,
                k,
                tuple(states),
                tuple(exchanges),
                len(evaluations),
                sweeps,
                neighbors_examined,
            )
        negative_count, ranks, outgoing_slot, incoming_rank = best
        exchanges.append(
            AcceptedExchange(outgoing_slot, incoming_rank, ranks, current_count, -negative_count)
        )
        states.append(SelectionState(ranks, evaluations[ranks]))
