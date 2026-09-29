"""Exact single-ticket best-response steepest ascent on BIG_LOTTO OFFICIAL_ANY_PRIZE.

Objective. The only objective is the exact OFFICIAL_ANY_PRIZE outcome count of a
K-ticket portfolio (special-number rescue included), as computed by
:func:`lottolab.research.b649_official_any_prize_exact.evaluate_portfolio`. A move
replaces exactly one retained ticket by any legal ticket that is not retained, and is
accepted only when it strictly raises that count. The ascent repeats the steepest
strict move until no single-ticket replacement improves the count. The claim at the
end is a single-ticket-replacement local optimum only; it says nothing about global
optimality, other neighborhoods, or any predictive edge.

Mechanism. An outcome is a main draw ``D`` plus a special ``s`` outside it, so it is
the 7-set ``W = D + {s}``, and a ticket ``t`` wins on it exactly when ``|t & W| >= 3``.
Every 7-set is produced by seven outcomes, so ``OFFICIAL_ANY_PRIZE_OUTCOME_COUNT`` is
``7 * COVERED_7SET_COUNT``. For the portfolio ``B`` without the replaced ticket, let
``U`` be its uncovered 7-sets and ``a_j(J) = #{W in U : J subset of W}``. Because
``1[m >= 3] = C(m,3) - 3 C(m,4) + 6 C(m,5) - 10 C(m,6)`` for ``0 <= m <= 6``, the gain
of a candidate ``t`` is

    gain(t) = sum_{J3 < t} a_3 - 3 sum_{J4 < t} a_4 + 6 sum_{J5 < t} a_5 - 10 a_6(t)

and all ``C(pool, 6)`` candidates are scored exactly from four small tables. The engine
is never scoring authority: every accepted move and each position's top candidate are
re-scored by the canonical evaluator, and any disagreement raises.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path

import numpy as np
import numpy.typing as npt

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
    verify_sealed_geometry_portfolio,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Columns = tuple[npt.NDArray[np.uint8], ...]
type Table = npt.NDArray[np.int64]

TICKET_SIZE = BIG_LOTTO_DRAW_SIZE
WINNING_SET_SIZE = TICKET_SIZE + 1
WIN_MATCHES = 3
MIN_POOL_SIZE = WINNING_SET_SIZE + 1
MAX_POOL_SIZE = 64
MAX_TIE_RANKS = 200_000
_CHUNK_ROWS = 1 << 20
_SCATTER_ROWS = 1 << 21
_TABLE_ORDERS = tuple(range(1, TICKET_SIZE))
# 1[m >= 3] = sum_j c_j C(m, j); the coefficients below are c_3, c_4, c_5, c_6.
_INCLUSION_EXCLUSION = {3: 1, 4: -3, 5: 6, 6: -10}


class BestResponseGateError(RuntimeError):
    """An engine self-check or canonical cross-check failed; the run must stop."""


@dataclass(frozen=True, slots=True)
class CandidateSpace:
    """Every ``TICKET_SIZE``-subset of the pool in colexicographic order (row == rank)."""

    pool_size: int
    columns6: Columns
    columns5: Columns
    columns4: Columns
    masks6: npt.NDArray[np.uint64]
    binom: tuple[npt.NDArray[np.int32], ...]

    @property
    def candidate_count(self) -> int:
        return int(self.masks6.size)

    @property
    def winning_set_count(self) -> int:
        return comb(self.pool_size, WINNING_SET_SIZE)

    def ticket_at(self, rank: int) -> Ticket:
        return tuple(int(column[rank]) + 1 for column in self.columns6)


@dataclass(frozen=True, slots=True)
class PositionSweep:
    """Exact scores of every legal replacement of the ticket at one position."""

    position: int
    removed: Ticket
    uncovered_without: int
    identity_gain: int
    best_gain: int
    best_count: int
    best_ranks: tuple[int, ...]
    sampled_gains: tuple[tuple[int, int], ...] = ()

    def covered_after(self, winning_set_count: int, gain: int) -> int:
        return winning_set_count - self.uncovered_without + gain


@dataclass(frozen=True, slots=True)
class AcceptedMove:
    iteration: int
    position: int
    removed: Ticket
    added: Ticket
    covered_before: int
    covered_after: int
    tie_count: int


@dataclass(frozen=True, slots=True)
class StepOutcome:
    covered_before: int
    sweeps: tuple[PositionSweep, ...]
    move: AcceptedMove | None
    portfolio: Portfolio


@dataclass(frozen=True, slots=True)
class AscentResult:
    pool_size: int
    start: Portfolio
    terminal: Portfolio
    moves: tuple[AcceptedMove, ...]
    sweeps_completed: int
    reached_local_optimum: bool


def canonical_portfolio(portfolio: Sequence[Sequence[int]]) -> Portfolio:
    """Tickets as sorted tuples, portfolio sorted lexicographically (the repository form)."""

    return tuple(sorted(tuple(sorted(ticket)) for ticket in portfolio))


def validate_portfolio(portfolio: Sequence[Sequence[int]], *, pool_size: int) -> Portfolio:
    """Return the canonical portfolio, or raise unless it is K distinct legal tickets."""

    if not portfolio:
        raise ValueError("portfolio must contain at least one ticket")
    for ticket in portfolio:
        if (
            len(ticket) != TICKET_SIZE
            or len(set(ticket)) != TICKET_SIZE
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(ticket)}")
    canonical = canonical_portfolio(portfolio)
    if len(set(canonical)) != len(canonical):
        raise ValueError("portfolio contains a duplicate ticket")
    return canonical


def ticket_rank(ticket: Sequence[int]) -> int:
    """Colexicographic rank of a ticket; equals its row in :class:`CandidateSpace`."""

    ordered = sorted(ticket)
    return sum(comb(number - 1, index + 1) for index, number in enumerate(ordered))


def _colex_columns(pool_size: int, size: int) -> Columns:
    columns: Columns = ()
    for width in range(1, size + 1):
        blocks: list[list[npt.NDArray[np.uint8]]] = [[] for _ in range(width)]
        for top in range(width - 1, pool_size):
            rows = comb(top, width - 1)
            for index in range(width - 1):
                blocks[index].append(columns[index][:rows])
            blocks[width - 1].append(np.full(rows, top, dtype=np.uint8))
        columns = tuple(np.concatenate(block) for block in blocks)
    return columns


def build_candidate_space(pool_size: int = BIG_LOTTO_POOL_SIZE) -> CandidateSpace:
    if not MIN_POOL_SIZE <= pool_size <= MAX_POOL_SIZE:
        raise ValueError(f"pool_size must be within {MIN_POOL_SIZE}..{MAX_POOL_SIZE}")
    columns6 = _colex_columns(pool_size, TICKET_SIZE)
    masks = np.zeros(columns6[0].size, dtype=np.uint64)
    for column in columns6:
        masks |= np.left_shift(np.uint64(1), column.astype(np.uint64))
    binom = (
        np.zeros(0, dtype=np.int32),
        *(
            np.array([comb(value, order) for value in range(pool_size)], dtype=np.int32)
            for order in _TABLE_ORDERS
        ),
    )
    return CandidateSpace(
        pool_size=pool_size,
        columns6=columns6,
        columns5=_colex_columns(pool_size, TICKET_SIZE - 1),
        columns4=_colex_columns(pool_size, TICKET_SIZE - 2),
        masks6=masks,
        binom=binom,
    )


def _ticket_mask(ticket: Sequence[int]) -> np.uint64:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return np.uint64(mask)


def _compute_a6(space: CandidateSpace, retained: Sequence[Ticket]) -> npt.NDArray[np.int32]:
    """``a_6(T)``: uncovered 7-sets ``T + y`` for every 6-set ``T`` (colex order)."""

    outside = space.pool_size - TICKET_SIZE
    masks = [_ticket_mask(ticket) for ticket in retained]
    table = np.empty(space.candidate_count, dtype=np.int32)
    zero = np.uint64(0)
    for start in range(0, space.candidate_count, _CHUNK_ROWS):
        stop = min(start + _CHUNK_ROWS, space.candidate_count)
        chunk = space.masks6[start:stop]
        dead = np.zeros(chunk.size, dtype=np.bool_)
        forbidden = np.zeros(chunk.size, dtype=np.uint64)
        for mask in masks:
            hits = np.bitwise_count(chunk & mask)
            dead |= hits >= WIN_MATCHES
            # A 7th number y keeps T + y uncovered only if it avoids b - T for every
            # retained ticket b that already shares WIN_MATCHES - 1 numbers with T.
            forbidden |= np.where(hits == WIN_MATCHES - 1, mask & ~chunk, zero)
        free = outside - np.bitwise_count(forbidden).astype(np.int32)
        table[start:stop] = np.where(dead, 0, free)
    return table


def _scatter_down(
    space: CandidateSpace,
    columns: Columns,
    values: npt.NDArray[np.float64],
    *,
    divisor: int,
) -> Table:
    """Sum ``values`` over every one-element extension of each subset, then divide exactly."""

    width = len(columns)
    out_size = comb(space.pool_size, width - 1)
    total = np.zeros(out_size, dtype=np.float64)
    for start in range(0, values.size, _SCATTER_ROWS):
        stop = min(start + _SCATTER_ROWS, values.size)
        weights = values[start:stop]
        parts = [
            [space.binom[order][column[start:stop]] for order in range(1, width)]
            for column in columns
        ]
        for drop in range(width):
            kept = [index for index in range(width) if index != drop]
            rank = parts[kept[0]][0]
            for order, index in enumerate(kept[1:], start=1):
                rank = rank + parts[index][order]
            total += np.bincount(rank, weights=weights, minlength=out_size)
    exact = np.rint(total).astype(np.int64)
    if bool(np.any(exact % divisor)):
        raise BestResponseGateError(
            f"width-{width - 1} table is not exactly divisible by {divisor}"
        )
    return exact // divisor


@dataclass(frozen=True, slots=True)
class _Tables:
    a3: Table
    a4: Table
    a5: Table
    a6: npt.NDArray[np.int32]
    uncovered: int


def _build_tables(space: CandidateSpace, retained: Sequence[Ticket]) -> _Tables:
    a6 = _compute_a6(space, retained)
    total = int(a6.sum(dtype=np.int64))
    if total % WINNING_SET_SIZE:
        raise BestResponseGateError("sum of a6 is not a multiple of 7")
    a5 = _scatter_down(space, space.columns6, a6.astype(np.float64), divisor=2)
    a4 = _scatter_down(space, space.columns5, a5.astype(np.float64), divisor=3)
    a3 = _scatter_down(space, space.columns4, a4.astype(np.float64), divisor=4)
    return _Tables(a3=a3, a4=a4, a5=a5, a6=a6, uncovered=total // WINNING_SET_SIZE)


def _all_gains(space: CandidateSpace, tables: _Tables) -> Table:
    gains = np.empty(space.candidate_count, dtype=np.int64)
    scaled = {
        3: tables.a3 * _INCLUSION_EXCLUSION[3],
        4: tables.a4 * _INCLUSION_EXCLUSION[4],
        5: tables.a5 * _INCLUSION_EXCLUSION[5],
    }
    subsets = {size: tuple(itertools.combinations(range(TICKET_SIZE), size)) for size in scaled}
    for start in range(0, space.candidate_count, _CHUNK_ROWS):
        stop = min(start + _CHUNK_ROWS, space.candidate_count)
        parts = [
            [space.binom[order][column[start:stop]] for order in _TABLE_ORDERS]
            for column in space.columns6
        ]
        acc = tables.a6[start:stop].astype(np.int64) * _INCLUSION_EXCLUSION[6]
        for size, table in scaled.items():
            for subset in subsets[size]:
                rank = parts[subset[0]][0]
                for order, index in enumerate(subset[1:], start=1):
                    rank = rank + parts[index][order]
                acc += table[rank]
        gains[start:stop] = acc
    return gains


def candidate_gains(
    space: CandidateSpace, portfolio: Sequence[Ticket], position: int
) -> tuple[Table, int, int]:
    """Exact gain of every candidate ticket when ``portfolio[position]`` is removed.

    Returns ``(gains, uncovered_without, identity_gain)``. ``gains[rank]`` is the number of
    7-sets the ticket of colex ``rank`` newly covers on top of the other tickets; every
    retained ticket is masked to ``-1`` so it can never be chosen as a replacement.
    """

    others = [ticket for index, ticket in enumerate(portfolio) if index != position]
    tables = _build_tables(space, others)
    gains = _all_gains(space, tables)
    identity_gain = int(gains[ticket_rank(portfolio[position])])
    for ticket in portfolio:
        gains[ticket_rank(ticket)] = -1
    return gains, tables.uncovered, identity_gain


def sweep_position(
    space: CandidateSpace,
    portfolio: Sequence[Ticket],
    position: int,
    *,
    sample_ranks: Sequence[int] = (),
) -> PositionSweep:
    gains, uncovered, identity_gain = candidate_gains(space, portfolio, position)
    best = int(gains.max())
    if best < 0:
        best_count, best_ranks = 0, ()
    else:
        tied = np.flatnonzero(gains == best)
        best_count = int(tied.size)
        best_ranks = tuple(int(rank) for rank in tied[:MAX_TIE_RANKS])
    return PositionSweep(
        position=position,
        removed=portfolio[position],
        uncovered_without=uncovered,
        identity_gain=identity_gain,
        best_gain=best,
        best_count=best_count,
        best_ranks=best_ranks,
        sampled_gains=tuple((rank, int(gains[rank])) for rank in sample_ranks),
    )


def choose_move(
    space: CandidateSpace,
    portfolio: Portfolio,
    sweeps: Sequence[PositionSweep],
    *,
    iteration: int,
) -> AcceptedMove | None:
    """The steepest strictly improving move, or ``None`` at a local optimum.

    Ties on the resulting covered-7-set count resolve to the lexicographically smallest
    resulting canonical portfolio, so the choice never depends on scan or input order.
    """

    total = space.winning_set_count
    current = {sweep.covered_after(total, sweep.identity_gain) for sweep in sweeps}
    if len(current) != 1:
        raise BestResponseGateError("positions disagree on the current covered 7-set count")
    (covered_before,) = current
    best_after = max(
        (sweep.covered_after(total, sweep.best_gain) for sweep in sweeps if sweep.best_count),
        default=covered_before,
    )
    if best_after <= covered_before:
        return None
    winners = [
        sweep
        for sweep in sweeps
        if sweep.best_count and sweep.covered_after(total, sweep.best_gain) == best_after
    ]
    if any(sweep.best_count > len(sweep.best_ranks) for sweep in winners):
        raise BestResponseGateError("improving tie set exceeds the retained tie limit")
    ties: list[tuple[Portfolio, int, Ticket]] = []
    for sweep in winners:
        rest = tuple(t for index, t in enumerate(portfolio) if index != sweep.position)
        for rank in sweep.best_ranks:
            added = space.ticket_at(rank)
            ties.append((canonical_portfolio((*rest, added)), sweep.position, added))
    _resulting, position, added = min(ties)
    return AcceptedMove(
        iteration=iteration,
        position=position,
        removed=portfolio[position],
        added=added,
        covered_before=covered_before,
        covered_after=best_after,
        tie_count=len(ties),
    )


def best_response_step(
    space: CandidateSpace,
    portfolio: Sequence[Sequence[int]],
    *,
    iteration: int = 1,
    sample_ranks: Sequence[int] = (),
) -> StepOutcome:
    """One steepest strict single-ticket replacement over the whole neighborhood."""

    start = validate_portfolio(portfolio, pool_size=space.pool_size)
    sweeps = tuple(
        sweep_position(space, start, position, sample_ranks=sample_ranks)
        for position in range(len(start))
    )
    move = choose_move(space, start, sweeps, iteration=iteration)
    covered_before = sweeps[0].covered_after(space.winning_set_count, sweeps[0].identity_gain)
    if move is None:
        return StepOutcome(covered_before, sweeps, None, start)
    rest = tuple(t for index, t in enumerate(start) if index != move.position)
    return StepOutcome(covered_before, sweeps, move, canonical_portfolio((*rest, move.added)))


def canonical_covered_sets(
    portfolio: Sequence[Sequence[int]], *, pool_size: int, draws: DrawMasks
) -> int:
    """Covered 7-set count from the canonical evaluator (outcome count / 7)."""

    exact = evaluate_portfolio(portfolio, pool_size=pool_size, draws=draws)
    if exact.official_any_prize_outcome_count % WINNING_SET_SIZE:
        raise BestResponseGateError("canonical outcome count is not a multiple of 7")
    return exact.official_any_prize_outcome_count // WINNING_SET_SIZE


def run_ascent(
    start: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    space: CandidateSpace | None = None,
    max_iterations: int | None = None,
    verify_samples: int = 0,
    seed: int = 0,
    resume_moves: Sequence[AcceptedMove] = (),
    on_move: Callable[[Portfolio, AcceptedMove], None] | None = None,
    progress: Callable[[str], None] | None = None,
) -> AscentResult:
    """Steepest strict ascent to a single-ticket-replacement local optimum.

    Canonical gates: the starting portfolio; every sweep's current count; each position's
    top replacement in every sweep; every accepted move; and, in the first sweep,
    ``verify_samples`` seeded random replacements per position.
    """

    def silent(_message: str) -> None:
        return None

    say: Callable[[str], None] = progress or silent
    space = space or build_candidate_space(pool_size)
    origin = validate_portfolio(start, pool_size=space.pool_size)
    draws = all_main_draw_masks(space.pool_size, TICKET_SIZE)
    total = space.winning_set_count
    portfolio = origin
    moves: list[AcceptedMove] = list(resume_moves)
    for move in moves:
        rest = tuple(t for t in portfolio if t != move.removed)
        portfolio = canonical_portfolio((*rest, move.added))
    covered = canonical_covered_sets(portfolio, pool_size=space.pool_size, draws=draws)
    sweeps_completed = len(moves)
    rng = random.Random(seed)

    def canonical_gate(candidate: Sequence[Ticket], expected: int, label: str) -> None:
        actual = canonical_covered_sets(candidate, pool_size=space.pool_size, draws=draws)
        if actual != expected:
            raise BestResponseGateError(f"{label}: engine {expected} != canonical {actual}")

    while max_iterations is None or sweeps_completed < max_iterations:
        iteration = sweeps_completed + 1
        sample_ranks: list[int] = []
        if iteration == 1 and verify_samples:
            retained = {ticket_rank(t) for t in portfolio}
            drawn = rng.sample(range(space.candidate_count), verify_samples + len(retained))
            sample_ranks = [rank for rank in drawn if rank not in retained][:verify_samples]
        started = time.monotonic()
        outcome = best_response_step(
            space, portfolio, iteration=iteration, sample_ranks=sample_ranks
        )
        if outcome.covered_before != covered:
            raise BestResponseGateError(
                f"sweep {iteration}: engine covered {outcome.covered_before} != canonical {covered}"
            )
        for sweep in outcome.sweeps:
            rest = tuple(t for index, t in enumerate(portfolio) if index != sweep.position)
            if sweep.best_count:
                top = space.ticket_at(sweep.best_ranks[0])
                canonical_gate(
                    (*rest, top),
                    sweep.covered_after(total, sweep.best_gain),
                    f"sweep {iteration} position {sweep.position} top replacement",
                )
            for rank, gain in sweep.sampled_gains:
                canonical_gate(
                    (*rest, space.ticket_at(rank)),
                    sweep.covered_after(total, gain),
                    f"sweep {iteration} position {sweep.position} sample rank {rank}",
                )
        say(f"sweep {iteration}: {time.monotonic() - started:.1f}s covered={covered}")
        sweeps_completed = iteration
        move = outcome.move
        if move is None:
            return AscentResult(
                space.pool_size, origin, portfolio, tuple(moves), sweeps_completed, True
            )
        canonical_gate(outcome.portfolio, move.covered_after, f"accepted move {iteration}")
        portfolio, covered = outcome.portfolio, move.covered_after
        moves.append(move)
        if on_move:
            on_move(portfolio, move)
    return AscentResult(space.pool_size, origin, portfolio, tuple(moves), sweeps_completed, False)


def _atomic_write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _move_payload(move: AcceptedMove) -> dict[str, object]:
    return {
        "iteration": move.iteration,
        "position": move.position,
        "removed": list(move.removed),
        "added": list(move.added),
        "covered_before": move.covered_before,
        "covered_after": move.covered_after,
        "tie_count": move.tie_count,
    }


def _load_moves(path: Path) -> tuple[AcceptedMove, ...]:
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        AcceptedMove(
            iteration=int(item["iteration"]),
            position=int(item["position"]),
            removed=tuple(item["removed"]),
            added=tuple(item["added"]),
            covered_before=int(item["covered_before"]),
            covered_after=int(item["covered_after"]),
            tie_count=int(item["tie_count"]),
        )
        for item in payload["moves"]
    )


def _describe(pool_size: int, portfolio: Portfolio) -> dict[str, object]:
    exact = evaluate_portfolio(portfolio, pool_size=pool_size)
    probability = exact.official_any_prize
    return {
        "official_any_prize_outcome_count": exact.official_any_prize_outcome_count,
        "official_any_prize_probability": f"{probability.numerator}/{probability.denominator}",
        "portfolio_sha256": canonical_portfolio_sha256(portfolio),
        "tickets": [list(ticket) for ticket in portfolio],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--ticket-count", type=int, choices=sorted(SEALED_GEOMETRY_PORTFOLIOS), default=10
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--verify-samples", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    pinned = SEALED_GEOMETRY_PORTFOLIOS[args.ticket_count]
    verify_sealed_geometry_portfolio(pinned)
    output: Path = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "state.json"

    baseline = _describe(BIG_LOTTO_POOL_SIZE, pinned.tickets)
    expected = pinned.official_any_prize_probability
    if baseline["official_any_prize_probability"] != f"{expected.numerator}/{expected.denominator}":
        raise BestResponseGateError("pinned portfolio no longer reproduces its sealed probability")

    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    moves_so_far = list(_load_moves(state_path))

    def record(_portfolio: Portfolio, move: AcceptedMove) -> None:
        moves_so_far.append(move)
        _atomic_write_json(state_path, {"moves": [_move_payload(m) for m in moves_so_far]})

    resumed = tuple(moves_so_far)
    result = run_ascent(
        pinned.tickets,
        max_iterations=args.max_iterations,
        verify_samples=args.verify_samples,
        seed=args.seed,
        resume_moves=resumed,
        on_move=record,
        progress=log,
    )

    # One fresh recomputation of the terminal portfolio, checked against the run's record.
    terminal = _describe(BIG_LOTTO_POOL_SIZE, result.terminal)
    baseline_count = int(str(baseline["official_any_prize_outcome_count"]))
    terminal_count = int(str(terminal["official_any_prize_outcome_count"]))
    recorded_count = (
        result.moves[-1].covered_after * WINNING_SET_SIZE if result.moves else baseline_count
    )
    reloaded = [tuple(ticket) for ticket in json.loads(json.dumps(terminal["tickets"]))]
    if (
        terminal_count != recorded_count
        or canonical_portfolio_sha256(reloaded) != terminal["portfolio_sha256"]
    ):
        raise BestResponseGateError("fresh terminal recomputation disagrees with the run")
    gain = terminal_count - baseline_count
    total_outcomes = comb(BIG_LOTTO_POOL_SIZE, TICKET_SIZE) * (BIG_LOTTO_POOL_SIZE - TICKET_SIZE)
    if gain > 0:
        verdict = f"STRICT_K{args.ticket_count}_GAIN"
    elif result.reached_local_optimum:
        verdict = f"NO_K{args.ticket_count}_GAIN"
    else:
        verdict = "INCOMPLETE"
    summary = {
        "ticket_count": args.ticket_count,
        "baseline": baseline,
        "terminal": terminal,
        "moves": [_move_payload(m) for m in result.moves],
        "sweeps_completed": result.sweeps_completed,
        "reached_local_optimum": result.reached_local_optimum,
        "fresh_recompute": "PASS",
        "gain_outcome_count": gain,
        "gain_pp": str(Fraction(gain * 100, total_outcomes)),
        "verdict": verdict,
        "local_optimum_claim": (
            "SINGLE_TICKET_REPLACEMENT_ONLY" if result.reached_local_optimum else "NOT_REACHED"
        ),
        "global_optimum_claim": "NO",
        "predictive_edge_claim": "NO",
    }
    _atomic_write_json(output / "result.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AcceptedMove",
    "AscentResult",
    "BestResponseGateError",
    "CandidateSpace",
    "PositionSweep",
    "StepOutcome",
    "best_response_step",
    "build_candidate_space",
    "candidate_gains",
    "canonical_covered_sets",
    "canonical_portfolio",
    "choose_move",
    "main",
    "run_ascent",
    "sweep_position",
    "ticket_rank",
    "validate_portfolio",
]
