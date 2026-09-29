"""Bounded elite recombination and path relinking for the B649 K20 portfolio.

Three stable K20 portfolios are supplied: the merged v5 champion (ELITE_A), the
merged v6 champion (ELITE_B) and the verified three-ticket-cycle candidate
(ELITE_C). Each is re-counted with the canonical evaluator and its SHA-256 is
checked before use; an input that does not reproduce is excluded and reported.

OFFICIAL_ANY_PRIZE success is a union over tickets: an outcome (main draw D,
special s) is won iff some single ticket wins it. Every outcome therefore has a
*winner pattern*, the set of pool tickets that win it, and the count of any
sub-portfolio is the number of outcomes whose pattern meets it.
``WinnerPatternHistogram`` builds that histogram once over the complete outcome
space (MAIN_DRAW_COLLAPSED_EXACT_SPECIAL_UNION, like the canonical evaluator)
and then scores any subset of the pool exactly in microseconds. It is a
regrouping of ``evaluate_portfolio``, not an approximation, and it is checked
against the canonical evaluator on the elites and on seeded random subsets.

Stages:

1. ``ELITE_TICKET_POOL``: the union of the distinct tickets of the valid elites.
2. Exhaustive pool solve: every K-subset of the pool is scored, so a maximum is
   *proven* for the pool (POOL_OPTIMALITY_STATUS=PROVEN_OPTIMAL). It says
   nothing about tickets outside the pool.
3. Beam path relinking for every ordered pair A -> B. A move swaps one ticket of
   A not in B for one ticket of B not in A, so the set distance to B falls by
   exactly one per step. The exploratory beam may decrease; BEST_EVER never does.
4. Optional bounded mutation: at most ``CYCLE_PROBES_PER_PATH`` probes per path,
   each applying the already-verified three-ticket single-number cycle operator
   to one seeded ticket triple of one beam-best state (one triple, at most 432
   raw attempts, one move). The operator lives in an unmerged commit and is
   loaded from that git object only after its SHA-256 matches the pinned value.

Every reported candidate is re-counted by the canonical evaluator, which is the
final arbiter. No historical outcome, predictive signal or float ranking is used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import random
import resource
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Scorer = Callable[[Portfolio], int]
type MaskArray = npt.NDArray[np.uint64]
type CountArray = npt.NDArray[np.int64]

TASK_ID = "B649_K20_ELITE_RECOMBINATION_PATH_RELINKING_PILOT_R1"
SCIENTIFIC_SCOPE = "BOUNDED_ELITE_RECOMBINATION_AND_PATH_RELINKING"
TICKET_COUNT = 20
BEAM_WIDTH = 32
CYCLE_PROBES_PER_PATH = 8
# The optional cycle stage runs only if the elite-ticket relinking stayed cheap.
CYCLE_STAGE_MAX_PATH_EVALUATIONS = 50_000
PARITY_SEED = 20260929
CYCLE_PROBE_SEED = 20260929
TRIPLE_RULE_HISTORY = (
    "A first draft picked the three tickets with the smallest exact marginal contribution. "
    "It was trial-run once (scratch output, not committed): no probe improved, and on ELITE_B "
    "the triple it selects, (7, 9, 10), has the lowest best-move delta of all 1140 triples in "
    "the committed full-family table of commit 3655b0f (-1493387; the best triples reach +14). "
    "It was replaced before the final run by the state-keyed seeded triple (TRIPLE_RULE). "
    "No probe outcome selected the seed."
)
PARITY_SAMPLE_COUNT = 24
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-elite-path-relinking-pilot-r1-result.json"
)

POOL_SOLVER = "EXHAUSTIVE_SUBSET_ENUMERATION_OVER_WINNER_PATTERN_HISTOGRAM"
POOL_PROVEN_OPTIMAL = "PROVEN_OPTIMAL"
POOL_NOT_PROVEN = "NOT_PROVEN"
_TIE_CAP = 4096
_SOLVER_BATCH = 1024
_HISTOGRAM_CHUNK = 1 << 17

CYCLE_OPERATOR_COMMIT = "7d3ea86ca9cf167344391a29e0a10d4630292559"
CYCLE_OPERATOR_PATH = "src/lottolab/research/b649_k20_three_ticket_single_number_cycle_r1.py"
CYCLE_OPERATOR_SHA256 = "79799744151daa638dd7a8bd372563fcb310c76825efb493415688983a6d5649"
_CYCLE_OPERATOR_MODULE_NAME = "_b649_k20_cycle_operator_7d3ea86"


class RelinkError(ValueError):
    """An input, evaluator or search contract was violated."""


@dataclass(frozen=True, slots=True)
class LotterySpec:
    pool_size: int = BIG_LOTTO_POOL_SIZE
    draw_size: int = BIG_LOTTO_DRAW_SIZE
    outright_matches: int = BIG_LOTTO_OUTRIGHT_MATCHES

    @property
    def special_count(self) -> int:
        return self.pool_size - self.draw_size

    @property
    def total_outcomes(self) -> int:
        return comb(self.pool_size, self.draw_size) * self.special_count


BIG_LOTTO = LotterySpec()


# --- identity -----------------------------------------------------------------------


def normalize_ticket(ticket: Sequence[int], *, lottery: LotterySpec = BIG_LOTTO) -> Ticket:
    if len(ticket) != lottery.draw_size:
        raise RelinkError(f"ticket must contain {lottery.draw_size} numbers")
    if any(type(number) is not int or not 1 <= number <= lottery.pool_size for number in ticket):
        raise RelinkError(f"illegal ticket numbers: {tuple(ticket)}")
    if len(set(ticket)) != lottery.draw_size:
        raise RelinkError("ticket numbers must be distinct")
    return tuple(sorted(ticket))


def normalize_portfolio(
    portfolio: Iterable[Sequence[int]],
    *,
    lottery: LotterySpec = BIG_LOTTO,
    expected_ticket_count: int | None = None,
) -> Portfolio:
    """Canonical set identity: sorted tickets, sorted portfolio, no duplicates."""

    normalized = [normalize_ticket(ticket, lottery=lottery) for ticket in portfolio]
    if expected_ticket_count is not None and len(normalized) != expected_ticket_count:
        raise RelinkError(f"portfolio must contain exactly {expected_ticket_count} tickets")
    if len(set(normalized)) != len(normalized):
        raise RelinkError("portfolio tickets must be distinct")
    return tuple(sorted(normalized))


def portfolio_sha256(portfolio: Portfolio) -> str:
    """SHA-256 of the compact JSON list of lists. The portfolio must be normalized."""

    payload = json.dumps([list(ticket) for ticket in portfolio], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_count(
    portfolio: Portfolio, *, draws: DrawMasks | None = None, lottery: LotterySpec = BIG_LOTTO
) -> int:
    """Read-only call to the canonical evaluator (the final arbiter)."""

    result = evaluate_portfolio(
        portfolio,
        pool_size=lottery.pool_size,
        draw_size=lottery.draw_size,
        outright_matches=lottery.outright_matches,
        draws=draws,
    )
    return int(result.official_any_prize_outcome_count)


def set_distance(state: Portfolio, target: Portfolio) -> int:
    """Number of tickets of ``state`` that are not in ``target``."""

    return len(set(state) - set(target))


@dataclass(frozen=True, slots=True)
class Candidate:
    portfolio: Portfolio
    sha256: str
    count: int


def make_candidate(portfolio: Portfolio, count: int) -> Candidate:
    return Candidate(portfolio, portfolio_sha256(portfolio), count)


def rank_key(candidate: Candidate) -> tuple[int, str]:
    """Higher exact count first, then the lowest normalized portfolio SHA-256."""

    return (-candidate.count, candidate.sha256)


# --- elite inputs -------------------------------------------------------------------


class EliteInputError(RelinkError):
    """A supplied elite could not be read or reproduced."""


@dataclass(frozen=True, slots=True)
class EliteSpec:
    label: str
    expected_count: int
    expected_sha256: str
    artifact_path: str
    artifact_field: str
    artifact_sha256: str
    git_commit: str | None = None


ELITE_SPECS: tuple[EliteSpec, ...] = (
    EliteSpec(
        label="ELITE_A",
        expected_count=312_986_016,
        expected_sha256="bc755e9b674e2ff37dac0fc8b52bb9f01bfd5a2bf90fc5f9f245dbb049c0ae86",
        artifact_path="docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json",
        artifact_field="TERMINAL_TICKETS",
        artifact_sha256="2deb616dc0c69dc0d6d41bc3d815f834f065c056b668a2e8db07b3a5064c05ea",
    ),
    EliteSpec(
        label="ELITE_B",
        expected_count=313_239_647,
        expected_sha256="0c52a1f0bed90cd47d08bb031b13c9bf693317493f88e45da8e087bd4a0ab65b",
        artifact_path=(
            "docs/research/matrix-native-results/"
            "b649-k20-two-ticket-joint-replacement-incumbent-r1.json"
        ),
        artifact_field="TICKETS",
        artifact_sha256="14f070a764a48a09007e18db212d491867a7c8dc59e775115391a02c8840f632",
    ),
    EliteSpec(
        label="ELITE_C",
        expected_count=313_239_661,
        expected_sha256="7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e",
        artifact_path=(
            "docs/research/matrix-native-results/"
            "b649-k20-three-ticket-cycle-full-family-r1-result.json"
        ),
        artifact_field="BEST_PORTFOLIO",
        artifact_sha256="2ba9308faa96518b8a75bb1ee8b1ddcf62e7cd66258c8f36999e48f68c676266",
        git_commit="3655b0f4bc43450748b4fc87c641d0acd11a8509",
    ),
)


@dataclass(frozen=True, slots=True)
class EliteRecord:
    spec: EliteSpec
    valid: bool
    reason: str
    portfolio: Portfolio
    sha256: str | None
    canonical_count: int | None

    @property
    def label(self) -> str:
        return self.spec.label


def _git_show(repo_root: Path, commit: str, path: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{path}"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise EliteInputError(f"git object {commit}:{path} is not readable") from error
    return completed.stdout


def _require_ticket_rows(value: object) -> list[list[int]]:
    if not isinstance(value, list):
        raise EliteInputError("elite ticket field must be a list")
    rows: list[list[int]] = []
    for row in cast(list[object], value):
        if not isinstance(row, list):
            raise EliteInputError("elite ticket rows must be lists")
        numbers = [number for number in cast(list[object], row) if type(number) is int]
        if len(numbers) != len(cast(list[object], row)):
            raise EliteInputError("elite ticket rows must be integer lists")
        rows.append(numbers)
    return rows


def read_elite_tickets(spec: EliteSpec, repo_root: Path) -> list[list[int]]:
    if spec.git_commit is not None:
        raw = _git_show(repo_root, spec.git_commit, spec.artifact_path)
    else:
        try:
            raw = (repo_root / spec.artifact_path).read_bytes()
        except OSError as error:
            raise EliteInputError(f"{spec.artifact_path} is not readable") from error
    if hashlib.sha256(raw).hexdigest() != spec.artifact_sha256:
        raise EliteInputError(f"{spec.artifact_path} bytes do not match the pinned sha256")
    payload: object = json.loads(raw)
    if not isinstance(payload, dict):
        raise EliteInputError("elite artifact must be a JSON object")
    return _require_ticket_rows(cast(dict[str, object], payload).get(spec.artifact_field))


def validate_elite(
    spec: EliteSpec,
    repo_root: Path,
    *,
    draws: DrawMasks,
    tickets: Sequence[Sequence[int]] | None = None,
) -> EliteRecord:
    """Read (or accept) an elite, then require its SHA-256 and canonical count to match."""

    try:
        rows = read_elite_tickets(spec, repo_root) if tickets is None else tickets
        portfolio = normalize_portfolio(rows, expected_ticket_count=TICKET_COUNT)
    except (RelinkError, ValueError, KeyError) as error:
        return EliteRecord(spec, False, f"{type(error).__name__}: {error}", (), None, None)
    digest = portfolio_sha256(portfolio)
    if digest != spec.expected_sha256:
        return EliteRecord(spec, False, f"portfolio sha256 {digest} != pinned", (), digest, None)
    count = canonical_count(portfolio, draws=draws)
    if count != spec.expected_count:
        return EliteRecord(spec, False, f"canonical count {count} != pinned", (), digest, count)
    return EliteRecord(spec, True, "OK", portfolio, digest, count)


def validate_elites(
    repo_root: Path, *, draws: DrawMasks, specs: Sequence[EliteSpec] = ELITE_SPECS
) -> tuple[EliteRecord, ...]:
    return tuple(validate_elite(spec, repo_root, draws=draws) for spec in specs)


def elite_ticket_pool(portfolios: Iterable[Portfolio]) -> tuple[Ticket, ...]:
    """Distinct tickets of the supplied portfolios, sorted. Nothing else is added."""

    return tuple(sorted({ticket for portfolio in portfolios for ticket in portfolio}))


# --- exact winner-pattern histogram --------------------------------------------------


@dataclass(frozen=True, slots=True)
class WinnerPatternHistogram:
    """Exact outcome counts grouped by the set of pool tickets that win them."""

    pool: tuple[Ticket, ...]
    lottery: LotterySpec
    keys: MaskArray
    counts: CountArray
    index_of: dict[Ticket, int]

    @property
    def total_outcomes(self) -> int:
        return int(self.counts.sum())

    def mask_of(self, portfolio: Iterable[Ticket]) -> int:
        mask = 0
        for ticket in portfolio:
            position = self.index_of.get(ticket)
            if position is None:
                raise RelinkError(f"ticket {ticket} is not in the histogram pool")
            mask |= 1 << position
        return mask

    def count_mask(self, mask: int) -> int:
        """Outcomes won by at least one ticket of the pool subset ``mask``."""

        hit = (self.keys & np.uint64(mask)) != 0
        return int(self.counts[hit].sum())

    def count(self, portfolio: Iterable[Ticket]) -> int:
        return self.count_mask(self.mask_of(portfolio))


def build_winner_pattern_histogram(
    pool: Sequence[Ticket],
    *,
    lottery: LotterySpec = BIG_LOTTO,
    draws: DrawMasks | None = None,
    chunk_size: int = _HISTOGRAM_CHUNK,
) -> WinnerPatternHistogram:
    """Group every (main draw, special) outcome by the pool tickets that win it.

    A ticket wins outright on a draw with ``>= outright_matches`` hits (every
    special) and wins the specials in ``ticket - D`` on a draw with exactly
    ``outright_matches - 1`` hits. This is the same rule the canonical evaluator
    unions over tickets.
    """

    if not 1 <= len(pool) <= 63:
        raise RelinkError("the pool must hold 1..63 tickets")
    if len(set(pool)) != len(pool):
        raise RelinkError("pool tickets must be distinct")
    if draws is None:
        draws = all_main_draw_masks(lottery.pool_size, lottery.draw_size)
    if draws.size != comb(lottery.pool_size, lottery.draw_size):
        raise RelinkError("draws must be the complete main-draw space")
    width = np.uint32 if len(pool) <= 32 else np.uint64
    one = np.uint64(1)
    zero = np.uint64(0)
    rescue_matches = lottery.outright_matches - 1
    ticket_masks = [np.uint64(ticket_mask(ticket)) for ticket in pool]
    shifts = np.arange(lottery.pool_size, dtype=np.uint64)
    histogram: dict[int, int] = {}
    for start in range(0, draws.size, chunk_size):
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=width)
        rescue = np.zeros((chunk.size, lottery.pool_size), dtype=width)
        for position, (ticket, mask) in enumerate(zip(pool, ticket_masks, strict=True)):
            bit = width(1 << position)
            hits = np.bitwise_count(chunk & mask)
            won |= np.where(hits >= lottery.outright_matches, bit, width(0))
            rescued = np.flatnonzero(hits == rescue_matches)
            if rescued.size:
                rescued_draws = chunk[rescued]
                for number in ticket:
                    outside = ((rescued_draws >> np.uint64(number - 1)) & one) == zero
                    rescue[rescued[outside], number - 1] |= bit
        special_free = ((chunk[:, None] >> shifts[None, :]) & one) == zero
        patterns = (won[:, None] | rescue)[special_free]
        values, occurrences = np.unique(patterns, return_counts=True)
        for value, occurrence in zip(values.tolist(), occurrences.tolist(), strict=True):
            histogram[value] = histogram.get(value, 0) + occurrence
    keys = np.array(sorted(histogram), dtype=np.uint64)
    counts = np.array([histogram[int(key)] for key in keys], dtype=np.int64)
    if int(counts.sum()) != lottery.total_outcomes:
        raise RelinkError("winner-pattern accounting does not cover the outcome space")
    return WinnerPatternHistogram(
        pool=tuple(pool),
        lottery=lottery,
        keys=keys,
        counts=counts,
        index_of={ticket: position for position, ticket in enumerate(pool)},
    )


# --- exhaustive pool solve ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolSolution:
    subsets_evaluated: int
    best: Candidate
    tie_count: int
    ties_truncated: bool


def _mask_rows(rows: Sequence[tuple[int, ...]], width: int) -> MaskArray:
    if width == 0:
        return np.zeros(len(rows), dtype=np.uint64)
    positions = np.array(rows, dtype=np.uint64)
    return np.bitwise_or.reduce(np.uint64(1) << positions, axis=1)


def solve_pool_exactly(
    histogram: WinnerPatternHistogram,
    ticket_count: int,
    *,
    batch_size: int = _SOLVER_BATCH,
    tie_cap: int = _TIE_CAP,
) -> PoolSolution:
    """Score every ``ticket_count``-subset of the pool; keep the exact maximum.

    Ties are broken by the lowest normalized portfolio SHA-256. Enumerating the
    smaller of (kept, dropped) sets keeps the count of combinations minimal.
    """

    pool_size = len(histogram.pool)
    if not 1 <= ticket_count <= pool_size:
        raise RelinkError("ticket_count must satisfy 1 <= ticket_count <= pool size")
    width = min(ticket_count, pool_size - ticket_count)
    enumerate_kept = width == ticket_count
    full = (1 << pool_size) - 1
    best = -1
    tie_count = 0
    ties: list[int] = []
    evaluated = 0
    combos = itertools.combinations(range(pool_size), width)
    while batch := list(itertools.islice(combos, batch_size)):
        masks = _mask_rows(batch, width)
        if not enumerate_kept:
            masks = np.uint64(full) ^ masks
        hit = (histogram.keys[None, :] & masks[:, None]) != 0
        totals = (hit * histogram.counts[None, :]).sum(axis=1)
        evaluated += len(batch)
        top = int(totals.max())
        if top < best:
            continue
        if top > best:
            best, tie_count, ties = top, 0, []
        winners = masks[totals == top]
        tie_count += int(winners.size)
        ties.extend(int(mask) for mask in winners[: max(tie_cap - len(ties), 0)])
    if evaluated != comb(pool_size, ticket_count):
        raise RelinkError("subset enumeration did not cover C(pool, K)")

    def portfolio_of(mask: int) -> Portfolio:
        return tuple(
            ticket for position, ticket in enumerate(histogram.pool) if mask >> position & 1
        )

    finalists = [make_candidate(portfolio_of(mask), best) for mask in ties]
    return PoolSolution(
        subsets_evaluated=evaluated,
        best=min(finalists, key=rank_key),
        tie_count=tie_count,
        ties_truncated=tie_count > len(ties),
    )


# --- beam path relinking -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Layer:
    depth: int
    distance_to_target: int
    generated: int
    deduplicated: int
    evaluated: int
    beam: tuple[Candidate, ...]
    best_ever_count: int

    @property
    def exploratory_best(self) -> Candidate:
        """CURRENT_EXPLORATORY_STATE of this depth. It may be worse than the last one."""

        return self.beam[0]


@dataclass(frozen=True, slots=True)
class PathResult:
    source_sha256: str
    target_sha256: str
    remove_set: tuple[Ticket, ...]
    add_set: tuple[Ticket, ...]
    layers: tuple[Layer, ...]
    best_ever: Candidate
    reached_target: bool
    generated: int
    deduplicated: int
    evaluations: int
    beam_expansions: int


def relink_path(
    source: Portfolio,
    target: Portfolio,
    score: Scorer,
    *,
    beam_width: int = BEAM_WIDTH,
    lottery: LotterySpec = BIG_LOTTO,
) -> PathResult:
    """Bounded beam search from ``source`` toward ``target``.

    Every move swaps one still-unmoved ticket of the current state (in the
    source, not in the target) for one target ticket not yet present, so the set
    distance to ``target`` drops by exactly one per depth. The beam is not
    required to improve. Each distinct state is scored once per path.
    """

    if beam_width < 1:
        raise RelinkError("beam_width must be positive")
    origin = normalize_portfolio(source, lottery=lottery)
    goal = normalize_portfolio(target, lottery=lottery, expected_ticket_count=len(origin))
    goal_set = set(goal)
    start = make_candidate(origin, score(origin))
    seen = {start.sha256}
    best_ever = start
    beam: tuple[Candidate, ...] = (start,)
    layers = [
        Layer(0, set_distance(origin, goal), 0, 0, 1, beam, best_ever.count),
    ]
    generated = deduplicated = beam_expansions = 0
    evaluations = 1
    depth = 0
    while layers[-1].distance_to_target > 0:
        children: dict[str, Candidate] = {}
        layer_generated = layer_deduplicated = 0
        for parent in beam:
            beam_expansions += 1
            state = set(parent.portfolio)
            for outgoing in sorted(state - goal_set):
                for incoming in sorted(goal_set - state):
                    layer_generated += 1
                    child = tuple(sorted((state - {outgoing}) | {incoming}))
                    digest = portfolio_sha256(child)
                    if digest in seen:
                        layer_deduplicated += 1
                        continue
                    seen.add(digest)
                    candidate = Candidate(child, digest, score(child))
                    children[digest] = candidate
                    if rank_key(candidate) < rank_key(best_ever):
                        best_ever = candidate
        generated += layer_generated
        deduplicated += layer_deduplicated
        evaluations += len(children)
        if not children:
            break
        depth += 1
        beam = tuple(sorted(children.values(), key=rank_key)[:beam_width])
        layers.append(
            Layer(
                depth,
                layers[-1].distance_to_target - 1,
                layer_generated,
                layer_deduplicated,
                len(children),
                beam,
                best_ever.count,
            )
        )
    return PathResult(
        source_sha256=start.sha256,
        target_sha256=portfolio_sha256(goal),
        remove_set=tuple(sorted(set(origin) - goal_set)),
        add_set=tuple(sorted(goal_set - set(origin))),
        layers=tuple(layers),
        best_ever=best_ever,
        reached_target=layers[-1].distance_to_target == 0,
        generated=generated,
        deduplicated=deduplicated,
        evaluations=evaluations,
        beam_expansions=beam_expansions,
    )


# --- optional bounded cycle mutation -------------------------------------------------


class ResidualLike(Protocol):
    def outcome_count(self, tickets: Sequence[Sequence[int]]) -> int: ...


class EmissionLike(Protocol):
    @property
    def portfolio(self) -> Portfolio: ...
    @property
    def sha256(self) -> str: ...
    @property
    def added(self) -> tuple[Ticket, ...]: ...
    @property
    def removed(self) -> tuple[Ticket, ...]: ...
    @property
    def numbers(self) -> tuple[int, int, int]: ...
    @property
    def direction(self) -> str: ...


class CycleOperator(Protocol):
    """The slice of the verified three-ticket cycle module this pilot uses."""

    def build_triple_residual(
        self,
        portfolio: Portfolio,
        indices: tuple[int, int, int],
        *,
        pool_size: int,
        draws: DrawMasks,
    ) -> ResidualLike: ...

    def iter_triple_cycle_specs(
        self, portfolio: Portfolio, indices: tuple[int, int, int], *, pool_size: int
    ) -> Iterator[object]: ...

    def emit_spec(
        self, portfolio: Portfolio, spec: object, *, pool_size: int
    ) -> EmissionLike | None: ...


def load_cycle_operator(
    repo_root: Path,
    *,
    commit: str = CYCLE_OPERATOR_COMMIT,
    path: str = CYCLE_OPERATOR_PATH,
    sha256: str = CYCLE_OPERATOR_SHA256,
) -> CycleOperator:
    """Load the verified cycle module from its pinned git object, SHA-256 first."""

    raw = _git_show(repo_root, commit, path)
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise EliteInputError("cycle operator source does not match the pinned sha256")
    spec = importlib.util.spec_from_loader(_CYCLE_OPERATOR_MODULE_NAME, loader=None)
    if spec is None:
        raise EliteInputError("cannot create a module spec for the cycle operator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_CYCLE_OPERATOR_MODULE_NAME] = module
    exec(compile(raw, f"<{commit}:{path}>", "exec"), module.__dict__)
    return cast(CycleOperator, module)


@dataclass(frozen=True, slots=True)
class CycleProbe:
    state_sha256: str
    state_count: int
    indices: tuple[int, int, int]
    triple_tickets: tuple[Ticket, ...]
    raw_attempts: int
    legal: int
    unique: int
    best: Candidate | None
    best_numbers: tuple[int, int, int] | None
    best_direction: str | None
    best_removed: tuple[Ticket, ...]
    best_added: tuple[Ticket, ...]
    seconds: float

    @property
    def improved(self) -> bool:
        return self.best is not None and self.best.count > self.state_count


def probe_triple(state: Candidate) -> tuple[int, int, int]:
    """Canonical positions of the one ticket triple this state's probe scans.

    A pseudo-random triple keyed by ``CYCLE_PROBE_SEED`` and the state's SHA-256,
    the same kind of seeded triple sample the earlier 20-triple pilot used. It
    reads neither the state's count nor its tickets, so no triple is favoured.
    """

    stream = random.Random(f"cycle-probe:{CYCLE_PROBE_SEED}:{state.sha256}")
    first, second, third = sorted(stream.sample(range(len(state.portfolio)), 3))
    return (first, second, third)


def probe_cycle(
    state: Candidate,
    operator: CycleOperator,
    draws: DrawMasks,
    *,
    lottery: LotterySpec = BIG_LOTTO,
) -> CycleProbe:
    """One triple, at most 6**3 * 2 raw attempts, at most one applied move."""

    began = time.perf_counter()
    indices = probe_triple(state)
    residual = operator.build_triple_residual(
        state.portfolio, indices, pool_size=lottery.pool_size, draws=draws
    )
    raw = legal = 0
    scored: dict[str, tuple[Candidate, EmissionLike]] = {}
    for spec in operator.iter_triple_cycle_specs(
        state.portfolio, indices, pool_size=lottery.pool_size
    ):
        raw += 1
        emission = operator.emit_spec(state.portfolio, spec, pool_size=lottery.pool_size)
        if emission is None:
            continue
        legal += 1
        if emission.sha256 in scored:
            continue
        count = residual.outcome_count(emission.added)
        scored[emission.sha256] = (Candidate(emission.portfolio, emission.sha256, count), emission)
    best_pair = min(scored.values(), key=lambda pair: rank_key(pair[0]), default=None)
    best = None if best_pair is None else best_pair[0]
    emission = None if best_pair is None else best_pair[1]
    return CycleProbe(
        state_sha256=state.sha256,
        state_count=state.count,
        indices=indices,
        triple_tickets=tuple(state.portfolio[index] for index in indices),
        raw_attempts=raw,
        legal=legal,
        unique=len(scored),
        best=best,
        best_numbers=None if emission is None else emission.numbers,
        best_direction=None if emission is None else emission.direction,
        best_removed=() if emission is None else emission.removed,
        best_added=() if emission is None else emission.added,
        seconds=time.perf_counter() - began,
    )


# --- orchestration ------------------------------------------------------------------


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak) if os.uname().sysname == "Darwin" else int(peak) * 1024


def _git_identity(repo_root: Path) -> dict[str, str]:
    def rev(expression: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", expression],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    return {"RUN_HEAD": rev("HEAD"), "RUN_TREE": rev("HEAD^{tree}")}


def _write_json_atomically(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(path.name + ".tmp")
    staging.write_bytes(encoded)
    os.replace(staging, path)
    return hashlib.sha256(encoded).hexdigest()


def _rows(portfolio: Portfolio) -> list[list[int]]:
    return [list(ticket) for ticket in portfolio]


def _candidate_json(candidate: Candidate) -> dict[str, object]:
    return {
        "COUNT": candidate.count,
        "EXACT_PROBABILITY": str(Fraction(candidate.count, BIG_LOTTO.total_outcomes)),
        "PORTFOLIO": _rows(candidate.portfolio),
        "SHA256": candidate.sha256,
    }


def _path_json(label: str, result: PathResult) -> dict[str, object]:
    return {
        "PATH": label,
        "SET_DISTANCE": len(result.remove_set),
        "REMOVE_SET": _rows(result.remove_set),
        "ADD_SET": _rows(result.add_set),
        "REACHED_TARGET": result.reached_target,
        "STATES_GENERATED": result.generated,
        "STATES_DEDUPLICATED": result.deduplicated,
        "EXACT_EVALUATIONS": result.evaluations,
        "BEAM_EXPANSIONS": result.beam_expansions,
        "BEST_EVER": _candidate_json(result.best_ever),
        "LAYERS": [
            {
                "DEPTH": layer.depth,
                "DISTANCE_TO_TARGET": layer.distance_to_target,
                "GENERATED": layer.generated,
                "DEDUPLICATED": layer.deduplicated,
                "EVALUATED": layer.evaluated,
                "BEAM_SIZE": len(layer.beam),
                "BEAM_WORST_COUNT": layer.beam[-1].count,
                "EXPLORATORY_BEST": _candidate_json(layer.exploratory_best),
                "BEST_EVER_COUNT": layer.best_ever_count,
            }
            for layer in result.layers
        ],
    }


def _probe_json(probe: CycleProbe, canonical: int | None) -> dict[str, object]:
    return {
        "STATE_SHA256": probe.state_sha256,
        "STATE_COUNT": probe.state_count,
        "TRIPLE_INDICES": list(probe.indices),
        "TRIPLE_TICKETS": _rows(probe.triple_tickets),
        "RAW_ATTEMPTS": probe.raw_attempts,
        "LEGAL": probe.legal,
        "UNIQUE": probe.unique,
        "BEST_COUNT": None if probe.best is None else probe.best.count,
        "BEST_SHA256": None if probe.best is None else probe.best.sha256,
        "BEST_NUMBERS": None if probe.best_numbers is None else list(probe.best_numbers),
        "BEST_DIRECTION": probe.best_direction,
        "BEST_REMOVED": _rows(probe.best_removed),
        "BEST_ADDED": _rows(probe.best_added),
        "BEST_DELTA_VS_STATE": None if probe.best is None else probe.best.count - probe.state_count,
        "IMPROVED_STATE": probe.improved,
        "CANONICAL_RECOUNT": canonical,
        "SECONDS": round(probe.seconds, 3),
    }


def run_pilot(repo_root: Path, *, result_path: Path) -> dict[str, object]:
    """Run every stage, recount every reported candidate canonically, write the result."""

    started = time.perf_counter()
    source = Path(__file__).resolve()
    draws = all_main_draw_masks(BIG_LOTTO.pool_size, BIG_LOTTO.draw_size)

    recounts: dict[str, int] = {}

    def recount(candidate: Candidate) -> int:
        if candidate.sha256 not in recounts:
            recounts[candidate.sha256] = canonical_count(candidate.portfolio, draws=draws)
        return recounts[candidate.sha256]

    elites = validate_elites(repo_root, draws=draws)
    valid = [elite for elite in elites if elite.valid]
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "SOURCE_MODULE_PATH": str(source.relative_to(repo_root.resolve())),
        "SOURCE_MODULE_SHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
        **_git_identity(repo_root),
        "TOTAL_OUTCOMES": BIG_LOTTO.total_outcomes,
        "BEAM_WIDTH": BEAM_WIDTH,
        "CYCLE_PROBES_PER_PATH": CYCLE_PROBES_PER_PATH,
        "ELITES": [
            {
                "LABEL": elite.label,
                "VALID": elite.valid,
                "REASON": elite.reason,
                "ARTIFACT_PATH": elite.spec.artifact_path,
                "ARTIFACT_FIELD": elite.spec.artifact_field,
                "ARTIFACT_SHA256": elite.spec.artifact_sha256,
                "GIT_COMMIT": elite.spec.git_commit,
                "EXPECTED_COUNT": elite.spec.expected_count,
                "EXPECTED_SHA256": elite.spec.expected_sha256,
                "CANONICAL_COUNT": elite.canonical_count,
                "SHA256": elite.sha256,
                "PORTFOLIO": _rows(elite.portfolio),
            }
            for elite in elites
        ],
        "VALID_ELITES": len(valid),
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "GLOBAL_OPTIMUM": "NOT_CLAIMED",
        "NOT_CLAIMED": [
            "global K20 optimum",
            "optimality outside the elite ticket pool",
            "exhaustive path optimality",
            "complete N3 or cycle-family local optimality",
            "gain versus protected Lane 3",
        ],
    }
    pool = elite_ticket_pool(elite.portfolio for elite in valid)
    if not valid or len(pool) < TICKET_COUNT:
        record.update(TASK_STATUS="BLOCKED_NO_VALID_ELITE", RECOMBINATION_GAIN_ESTABLISHED="NO")
        _write_json_atomically(result_path, record)
        return record
    best_input = max(elite.canonical_count or 0 for elite in valid)
    record["ELITE_TICKET_POOL_SIZE"] = len(pool)
    record["ELITE_TICKET_POOL"] = _rows(pool)
    record["BEST_INPUT_ELITE_COUNT"] = best_input

    began = time.perf_counter()
    histogram = build_winner_pattern_histogram(pool, draws=draws)
    histogram_seconds = time.perf_counter() - began

    def pool_score(portfolio: Portfolio) -> int:
        return histogram.count(portfolio)

    rng = random.Random(PARITY_SEED)
    parity_subsets = [
        tuple(pool[index] for index in sorted(rng.sample(range(len(pool)), TICKET_COUNT)))
        for _ in range(PARITY_SAMPLE_COUNT)
    ]
    parity_pairs = [(pool_score(e.portfolio), e.canonical_count or 0) for e in valid]
    parity_pairs += [(pool_score(p), canonical_count(p, draws=draws)) for p in parity_subsets]
    parity_mismatches = sum(1 for fast, slow in parity_pairs if fast != slow)
    record["EVALUATOR_PARITY"] = {
        "ELITES_CHECKED": len(valid),
        "SEEDED_RANDOM_SUBSETS": PARITY_SAMPLE_COUNT,
        "SEED": PARITY_SEED,
        "MISMATCHES": parity_mismatches,
        "HISTOGRAM_DISTINCT_PATTERNS": int(histogram.keys.size),
        "HISTOGRAM_SECONDS": round(histogram_seconds, 3),
    }
    if parity_mismatches:
        record.update(TASK_STATUS="BLOCKED_EVALUATOR_PARITY", RECOMBINATION_GAIN_ESTABLISHED="NO")
        _write_json_atomically(result_path, record)
        return record

    began = time.perf_counter()
    solution = solve_pool_exactly(histogram, TICKET_COUNT)
    solver_seconds = time.perf_counter() - began
    pool_recount = recount(solution.best)
    record["POOL_SOLVER"] = POOL_SOLVER
    # Every C(P, K) subset was scored by an evaluator with zero parity mismatches.
    record["POOL_OPTIMALITY_STATUS"] = (
        POOL_PROVEN_OPTIMAL if pool_recount == solution.best.count else POOL_NOT_PROVEN
    )
    record["POOL"] = {
        "SUBSETS_EVALUATED": solution.subsets_evaluated,
        "SUBSETS_EXPECTED": comb(len(pool), TICKET_COUNT),
        "BEST": _candidate_json(solution.best),
        "TIE_COUNT": solution.tie_count,
        "TIES_TRUNCATED": solution.ties_truncated,
        "CANONICAL_RECOUNT": pool_recount,
        "SECONDS": round(solver_seconds, 3),
    }

    labels = {elite.label: elite for elite in valid}
    path_results: dict[str, PathResult] = {}
    began = time.perf_counter()
    for source_label, target_label in itertools.permutations(sorted(labels), 2):
        path_results[f"{source_label}->{target_label}"] = relink_path(
            labels[source_label].portfolio, labels[target_label].portfolio, pool_score
        )
    path_seconds = time.perf_counter() - began
    path_totals = {
        "PATH_PAIRS": len(path_results),
        "PATH_STATES_GENERATED": sum(r.generated for r in path_results.values()),
        "PATH_STATES_DEDUPLICATED": sum(r.deduplicated for r in path_results.values()),
        "EXACT_EVALUATIONS": sum(r.evaluations for r in path_results.values()),
        "BEAM_EXPANSIONS": sum(r.beam_expansions for r in path_results.values()),
    }
    reported: dict[str, Candidate] = {solution.best.sha256: solution.best}
    for result in path_results.values():
        reported[result.best_ever.sha256] = result.best_ever
        for layer in result.layers:
            reported[layer.exploratory_best.sha256] = layer.exploratory_best
    path_recount_mismatches = 0
    for candidate in reported.values():
        if recount(candidate) != candidate.count:
            path_recount_mismatches += 1
    path_best = min((r.best_ever for r in path_results.values()), key=rank_key, default=None)
    record["PATHS"] = [_path_json(label, result) for label, result in path_results.items()]
    record["PATH_STAGE"] = {
        **path_totals,
        "SECONDS": round(path_seconds, 3),
        "REPORTED_CANDIDATES_RECOUNTED": len(reported),
        "RECOUNT_MISMATCHES": path_recount_mismatches,
        "BEST_EVER": None if path_best is None else _candidate_json(path_best),
    }

    cycle_stage: dict[str, object] = {"STATUS": "NOT_RUN"}
    cycle_candidates: list[Candidate] = []
    probes_used = cycle_residual_evaluations = 0
    if path_totals["EXACT_EVALUATIONS"] > CYCLE_STAGE_MAX_PATH_EVALUATIONS:
        cycle_stage["REASON"] = "path stage exceeded the cheap-finish bound"
    elif not path_results:
        cycle_stage["REASON"] = "no relinking path"
    else:
        try:
            operator = load_cycle_operator(repo_root)
        except EliteInputError as error:
            cycle_stage["REASON"] = f"cycle operator unavailable: {error}"
        else:
            began = time.perf_counter()
            probe_cache: dict[str, CycleProbe] = {}
            per_path: dict[str, list[str]] = {}
            for label, result in path_results.items():
                states = [layer.exploratory_best for layer in result.layers][:CYCLE_PROBES_PER_PATH]
                per_path[label] = [state.sha256 for state in states]
                probes_used += len(states)
                for state in states:
                    if state.sha256 not in probe_cache:
                        probe_cache[state.sha256] = probe_cycle(state, operator, draws)
            probe_rows: list[dict[str, object]] = []
            cycle_residual_evaluations = sum(probe.unique for probe in probe_cache.values())
            for probe in probe_cache.values():
                canonical = None
                if probe.improved and probe.best is not None:
                    canonical = recount(probe.best)
                    cycle_candidates.append(probe.best)
                probe_rows.append(_probe_json(probe, canonical))
            cycle_stage = {
                "STATUS": "COMPLETE",
                "OPERATOR_COMMIT": CYCLE_OPERATOR_COMMIT,
                "OPERATOR_SHA256": CYCLE_OPERATOR_SHA256,
                "TRIPLE_RULE": (
                    "one pseudo-random ticket triple per beam-best state, keyed by "
                    f"random.Random('cycle-probe:{CYCLE_PROBE_SEED}:<state sha256>')"
                ),
                "TRIPLE_RULE_HISTORY": TRIPLE_RULE_HISTORY,
                "PROBES_USED": probes_used,
                "DISTINCT_STATES_PROBED": len(probe_cache),
                "PROBES_PER_PATH": {label: len(shas) for label, shas in per_path.items()},
                "IMPROVING_PROBES": len(cycle_candidates),
                "PROBES": probe_rows,
                "SECONDS": round(time.perf_counter() - began, 3),
            }
    record["CYCLE_STAGE"] = cycle_stage

    finalists = [solution.best, *[r.best_ever for r in path_results.values()], *cycle_candidates]
    final = min(finalists, key=rank_key)
    final_recount = recount(final)
    gain = final.count > best_input and final_recount == final.count
    record.update(
        BEST_FINAL=_candidate_json(final),
        BEST_FINAL_CANONICAL_RECOUNT=final_recount,
        BEST_CANONICAL_RECOUNT_STATUS="PASS" if final_recount == final.count else "FAIL",
        BEST_FINAL_COUNT=final.count,
        BEST_DELTA=final.count - best_input,
        BEST_PORTFOLIO_SHA256=final.sha256,
        RECOMBINATION_GAIN_ESTABLISHED="YES" if gain else "NO",
        RESULT="RECOMBINATION_GAIN" if gain else "NO_IMPROVEMENT_IN_BOUNDED_RECOMBINATION",
        CANONICAL_RECOUNTS=len(recounts),
        METRICS={
            "VALID_ELITES": len(valid),
            "ELITE_TICKET_POOL_SIZE": len(pool),
            **path_totals,
            "POOL_SUBSET_EVALUATIONS": solution.subsets_evaluated,
            "CYCLE_PROBES_USED": probes_used,
            "CYCLE_RESIDUAL_EVALUATIONS": cycle_residual_evaluations,
            "CANONICAL_RECOUNTS": len(recounts),
            "WALL_SECONDS": round(time.perf_counter() - started, 3),
            "PEAK_RSS_BYTES": _peak_rss_bytes(),
            "BEST_INPUT_ELITE_COUNT": best_input,
            "BEST_FINAL_COUNT": final.count,
            "BEST_DELTA": final.count - best_input,
        },
        TASK_STATUS="COMPLETE" if path_recount_mismatches == 0 else "BLOCKED_RECOUNT_MISMATCH",
    )
    _write_json_atomically(result_path, record)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded K20 elite path-relinking pilot (R1).")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, default=None)
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root
    result_path: Path = args.result_path or repo_root / RESULT_PATH
    record = run_pilot(repo_root, result_path=result_path)
    keys = ("TASK_STATUS", "BEST_FINAL_COUNT", "BEST_DELTA", "RECOMBINATION_GAIN_ESTABLISHED")
    print(json.dumps({key: record.get(key) for key in keys}, sort_keys=True))
    return 0 if record["TASK_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
