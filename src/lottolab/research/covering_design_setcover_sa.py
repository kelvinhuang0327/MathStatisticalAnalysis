"""Research-only covering-design port of RowVoi's simulated-annealing set cover.

The covering-design mapping is exact: the universe is every t-subset of
``range(v)``, each selectable unit-cost set is one k-block, and a block covers
the t-subsets contained in it.  The initial state is the donor greedy cover.
Each annealing step then removes one selected block or adds one unselected
block, hard-rejects incomplete covers, and uses selected-block cardinality as
the objective.

The donor's unspecified traversal and process-global randomness are replaced
only by canonical lexicographic block traversal and ``random.Random(seed)``.

* ``PYTHON_PORT_REPRODUCIBLE: YES`` when no wall-clock cutoff is supplied;
* ``DONOR_EXACT_TRAJECTORY_PARITY: NOT_CLAIMED``;
* ``ALGORITHM_RULE_PARITY: CHARACTERIZATION_PASS_REQUIRED``;
* ``TIME_LIMIT_TRAJECTORY_REPRODUCIBILITY: NOT_CLAIMED``.

The ``v <= 12`` guard is an R1 execution-safety wrapper, not a limitation of
the donor algorithm.  This module is not a fixed-ticket-count optimizer, a
production lottery strategy, a historical-data method, a replay method, a
ranking candidate, or a Matrix method.

Third-party provenance
----------------------

Algorithm and code structure ported from ``gojiplus/rowvoi``, method
``SetCoverProblem._simulated_annealing`` in ``rowvoi/setcover.py``, at commit
``64b921cf25f9a4a03787be1a73be679cfbece81f``, licensed under the MIT License.
The required donor notice is retained here because this module incorporates a
substantial port of the donor implementation.

MIT License

Copyright (c) 2025 goji+

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import itertools
import math
import random
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Subset = tuple[int, ...]
Block = tuple[int, ...]
BlockSnapshot = tuple[Block, ...]
TerminationReason = Literal["TEMPERATURE_FLOOR", "TIME_LIMIT"]

_INITIAL_TEMPERATURE = 10.0
_COOLING_RATE = 0.95
_TEMPERATURE_FLOOR = 0.01
_MAX_R1_V = 12


def _require_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _require_time_limit(value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("time_limit_seconds must be a finite positive number or None")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("time_limit_seconds must be a finite positive number or None")


@dataclass(frozen=True, slots=True)
class CoveringDesignSAConfig:
    """Caller-owned randomness and optional donor-style wall-clock cutoff."""

    seed: int
    time_limit_seconds: float | None = None

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_time_limit(self.time_limit_seconds)


@dataclass(frozen=True, slots=True)
class CoveringDesignSAResult:
    """Canonical best exact cover and observable annealing termination state."""

    selected_blocks: BlockSnapshot
    block_count: int
    coverage: float
    temperature_steps: int
    termination_reason: TerminationReason


@dataclass(frozen=True, slots=True)
class _CoveringDesignSetCoverProblem:
    """Fully enumerated bounded covering-design set-cover instance."""

    v: int
    k: int
    t: int
    universe: tuple[Subset, ...]
    blocks: tuple[Block, ...]
    covered_by_block: dict[Block, frozenset[Subset]]


def _validate_domain(v: int, k: int, t: int) -> None:
    _require_integer("v", v)
    _require_integer("k", k)
    _require_integer("t", t)
    if not v > k > t >= 1:
        raise ValueError("configuration requires v > k > t >= 1")
    if v > _MAX_R1_V:
        raise ValueError("R1 research execution requires v <= 12")


def _build_problem(v: int, k: int, t: int) -> _CoveringDesignSetCoverProblem:
    """Enumerate the bounded exact covering-design set-cover mapping."""

    _validate_domain(v, k, t)
    universe = tuple(itertools.combinations(range(v), t))
    blocks = tuple(itertools.combinations(range(v), k))
    covered_by_block = {
        block: frozenset(itertools.combinations(block, t)) for block in blocks
    }
    return _CoveringDesignSetCoverProblem(v, k, t, universe, blocks, covered_by_block)


def _covered_t_subsets(
    problem: _CoveringDesignSetCoverProblem, selected: Iterable[Block]
) -> set[Subset]:
    covered: set[Subset] = set()
    for block in selected:
        covered.update(problem.covered_by_block[block])
    return covered


def _coverage(
    problem: _CoveringDesignSetCoverProblem, selected: Iterable[Block]
) -> float:
    return len(_covered_t_subsets(problem, selected)) / len(problem.universe)


def _is_exact_cover(
    problem: _CoveringDesignSetCoverProblem, selected: Iterable[Block]
) -> bool:
    return len(_covered_t_subsets(problem, selected)) == len(problem.universe)


def _greedy_cover(problem: _CoveringDesignSetCoverProblem) -> BlockSnapshot:
    """Return donor greedy order with canonical lexicographic tie traversal."""

    selected: list[Block] = []
    selected_set: set[Block] = set()
    uncovered = set(problem.universe)

    while uncovered:
        best_block: Block | None = None
        best_cost_ratio = float("inf")
        for block in problem.blocks:
            if block in selected_set:
                continue
            gain = len(uncovered.intersection(problem.covered_by_block[block]))
            if gain > 0:
                cost_ratio = 1.0 / gain
                if cost_ratio < best_cost_ratio:
                    best_block = block
                    best_cost_ratio = cost_ratio

        if best_block is None:
            raise RuntimeError("bounded covering-design universe is not coverable")
        selected.append(best_block)
        selected_set.add(best_block)
        uncovered.difference_update(problem.covered_by_block[best_block])

    return tuple(selected)


def _generate_neighbor(
    current: set[Block], blocks: tuple[Block, ...], rng: random.Random
) -> set[Block]:
    """Generate exactly one donor add/remove move, or the donor add no-op."""

    neighbor = current.copy()
    if rng.random() < 0.5 and len(neighbor) > 1:
        neighbor.remove(rng.choice(sorted(neighbor)))
    else:
        candidates = [block for block in blocks if block not in neighbor]
        if candidates:
            neighbor.add(rng.choice(candidates))
    return neighbor


def _accept_neighbor(delta: int, temperature: float, rng: random.Random) -> bool:
    """Apply the donor's strict-improvement-or-Metropolis acceptance rule."""

    return delta < 0 or rng.random() < math.exp(-delta / temperature)


class _SimulatedAnnealingSearch:
    """Stateful donor-style SA over one bounded covering-design problem."""

    def __init__(self, problem: _CoveringDesignSetCoverProblem, rng: random.Random) -> None:
        self.problem = problem
        self.rng = rng
        self.current = set(_greedy_cover(problem))
        self.current_cost = len(self.current)
        self.best = self.current.copy()
        self.best_cost = self.current_cost
        self.temperature = _INITIAL_TEMPERATURE
        self.temperature_steps = 0

    def _update_best(self) -> None:
        if self.current_cost < self.best_cost:
            self.best = self.current.copy()
            self.best_cost = self.current_cost

    def attempt_neighbor(self) -> None:
        neighbor = _generate_neighbor(self.current, self.problem.blocks, self.rng)
        if _is_exact_cover(self.problem, neighbor):
            neighbor_cost = len(neighbor)
            delta = neighbor_cost - self.current_cost
            if _accept_neighbor(delta, self.temperature, self.rng):
                self.current = neighbor
                self.current_cost = neighbor_cost
                self._update_best()

        self.temperature *= _COOLING_RATE
        self.temperature_steps += 1

    def run(self, time_limit_seconds: float | None) -> TerminationReason:
        start_time = time.time()
        while self.temperature > _TEMPERATURE_FLOOR:
            if (
                time_limit_seconds is not None
                and time.time() - start_time > time_limit_seconds
            ):
                return "TIME_LIMIT"
            self.attempt_neighbor()
        return "TEMPERATURE_FLOOR"


def run_covering_design_setcover_sa(
    v: int,
    k: int,
    t: int,
    *,
    config: CoveringDesignSAConfig,
) -> CoveringDesignSAResult:
    """Run the research-only RowVoi set-cover SA on a bounded exact design."""

    problem = _build_problem(v, k, t)
    search = _SimulatedAnnealingSearch(problem, random.Random(config.seed))
    termination_reason = search.run(config.time_limit_seconds)
    selected_blocks = tuple(sorted(search.best))
    coverage = _coverage(problem, selected_blocks)
    if coverage != 1.0:
        raise RuntimeError("simulated annealing returned an incomplete covering design")

    return CoveringDesignSAResult(
        selected_blocks=selected_blocks,
        block_count=len(selected_blocks),
        coverage=coverage,
        temperature_steps=search.temperature_steps,
        termination_reason=termination_reason,
    )


__all__ = [
    "CoveringDesignSAConfig",
    "CoveringDesignSAResult",
    "run_covering_design_setcover_sa",
]
