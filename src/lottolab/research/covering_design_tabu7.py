"""Research-only Python port of the pinned CoveringDesignProblem TabuSearch7.

The implementation is a bounded, reproducible port of the donor's
block-deletion and one-element-exchange repair loop.  It deliberately keeps
the donor's exact t-subset coverage authority, zero-active-objective delta,
tabu directionality, perturbation mechanics, and characterized perturbation
tie-condition bug.  ``max_iterations`` is an explicit wrapper cutoff; it is
not a donor convergence criterion.

Reproducibility boundary:

* ``PYTHON_PORT_REPRODUCIBLE: YES`` for identical inputs, seeds, and bounds;
* ``JAVA_PYTHON_TRAJECTORY_PARITY: NOT_CLAIMED`` because the donor uses
  unspecified Java ``HashSet`` traversal and an unseeded ``Random``;
* ``ALGORITHM_RULE_PARITY: CHARACTERIZATION_PASS_REQUIRED``.

The donor wrapper's hard-coded ``intersection >= 2`` solution check was
characterized as pair-specific and is not ported as a generic validator.
``DONOR_WRAPPER_PAIR_CHECK: NOT_PORTED_AS_GENERIC_VALIDATOR``.
For every supported ``t``, exact complete coverage means that every required
t-subset is covered and therefore that the conflict count is zero.

This module is not a production lottery strategy, a fixed-ticket strategy,
a prediction method, a replay method, a ranking candidate, or a Matrix
method.

Third-party provenance
----------------------

Algorithm and code structure ported from
``DelieverThibaut/CoveringDesignProblem`` at commit
``e3e277772a0c5f2e8959feec592dedee223f2f6d`` by Thibaut Deliever, licensed
under the MIT License.  The donor notice is retained here because this
research module incorporates a substantial port of the donor implementation.

MIT License

Copyright (c) 2024 Thibaut Deliever

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
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Subset = tuple[int, ...]
BlockValue = tuple[int, ...]
BlockSnapshot = tuple[BlockValue, ...]
TerminationReason = Literal["ITERATION_LIMIT"]


def _require_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


@dataclass(frozen=True, slots=True)
class TabuSearch7RunConfig:
    """Caller-owned seeds and bounded-search cutoff for the research port."""

    constructor_seed: int
    search_seed: int
    max_iterations: int

    def __post_init__(self) -> None:
        _require_integer("constructor_seed", self.constructor_seed)
        _require_integer("search_seed", self.search_seed)
        _require_integer("max_iterations", self.max_iterations)
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")


@dataclass(frozen=True, slots=True)
class TabuSearch7Result:
    """Observable bounded-run state, with complete and current solutions separate."""

    best_complete_blocks: BlockSnapshot
    final_blocks: BlockSnapshot
    final_conflicts: int
    iterations: int
    termination_reason: TerminationReason


@dataclass(eq=False, slots=True)
class _Block:
    identifier: int
    elements: set[int]
    covered_t_subsets: set[Subset] = field(default_factory=lambda: set[Subset]())

    def recompute_covered_t_subsets(self, t: int) -> None:
        self.covered_t_subsets = {
            tuple(subset) for subset in itertools.combinations(sorted(self.elements), t)
        }

    def add_t_subset(self, t_subset: Subset, t: int) -> None:
        self.elements.update(t_subset)
        self.recompute_covered_t_subsets(t)

    def add_element(self, element: int, t: int) -> None:
        self.elements.add(element)
        self.recompute_covered_t_subsets(t)

    def replace_element(self, outgoing: int, incoming: int, t: int) -> None:
        if outgoing not in self.elements:
            raise ValueError("outgoing element is not in the block")
        if incoming in self.elements:
            raise ValueError("incoming element is already in the block")
        self.elements.remove(outgoing)
        self.elements.add(incoming)
        self.recompute_covered_t_subsets(t)


class _CoveringDesign:
    """Exact t-subset coverage state used by the translated donor core."""

    def __init__(self, v: int, k: int, t: int) -> None:
        self.v = v
        self.k = k
        self.t = t
        # This is the explicit canonical replacement for donor HashSet order.
        self.all_t_subsets: tuple[Subset, ...] = tuple(itertools.combinations(range(v), t))
        self.coverage: dict[Subset, set[int]] = {
            subset: set() for subset in self.all_t_subsets
        }
        self.uncovered_t_subsets: set[Subset] = set(self.all_t_subsets)
        self.blocks: list[_Block] = []
        self._next_block_identifier = 0

    @classmethod
    def from_blocks(
        cls, v: int, k: int, t: int, block_values: Iterable[Iterable[int]]
    ) -> _CoveringDesign:
        """Build exact state from full-size blocks for bounded characterization tests."""

        design = cls(v, k, t)
        for block_value in block_values:
            elements = set(block_value)
            if len(elements) != k:
                raise ValueError("test block must contain exactly k distinct elements")
            if not elements.issubset(range(v)):
                raise ValueError("test block element is outside the universe")
            block = design.new_block(elements)
            design.add_block(block)
        return design

    def new_block(self, elements: Iterable[int] = ()) -> _Block:
        block = _Block(self._next_block_identifier, set(elements))
        self._next_block_identifier += 1
        block.recompute_covered_t_subsets(self.t)
        return block

    def add_block(self, block: _Block) -> None:
        self.blocks.append(block)
        for subset in sorted(block.covered_t_subsets):
            self.coverage[subset].add(block.identifier)
            self.uncovered_t_subsets.discard(subset)

    def remove_block(self, block: _Block) -> None:
        if block not in self.blocks:
            raise ValueError("block is not in the covering design")
        for subset in sorted(block.covered_t_subsets):
            holders = self.coverage[subset]
            holders.remove(block.identifier)
            if not holders:
                self.uncovered_t_subsets.add(subset)
        self.blocks.remove(block)

    def replace_element(self, block: _Block, outgoing: int, incoming: int) -> None:
        if block not in self.blocks:
            raise ValueError("block is not in the covering design")

        affected_subsets = sorted(
            subset for subset in block.covered_t_subsets if outgoing in subset
        )
        for old_subset in affected_subsets:
            old_holders = self.coverage[old_subset]
            old_holders.remove(block.identifier)
            if not old_holders:
                self.uncovered_t_subsets.add(old_subset)

            new_subset = tuple(
                sorted((*((element for element in old_subset if element != outgoing)), incoming))
            )
            self.coverage[new_subset].add(block.identifier)
            self.uncovered_t_subsets.discard(new_subset)

        block.replace_element(outgoing, incoming, self.t)

    def conflict_count(self) -> int:
        return len(self.uncovered_t_subsets)

    def coverage_count(self, subset: Subset) -> int:
        return len(self.coverage[subset])


def _snapshot_blocks(blocks: Iterable[_Block]) -> BlockSnapshot:
    """Return a canonical value snapshot, independent of block object identity."""

    return tuple(sorted(tuple(sorted(block.elements)) for block in blocks))


def _construct_initial_design(v: int, k: int, t: int, rng: random.Random) -> _CoveringDesign:
    """Translate CoveringDesignConstructor with canonical t-subset traversal."""

    design = _CoveringDesign(v, k, t)
    open_block = design.new_block()

    def add_open_block_to_design() -> _Block:
        # The donor pads and adds even an empty final open block.  That final
        # call is observable when the last t-subset exactly filled a block.
        while len(open_block.elements) < design.k:
            random_element = rng.randrange(design.v)
            while random_element in open_block.elements:
                random_element = rng.randrange(design.v)
            open_block.add_element(random_element, design.t)
        design.add_block(open_block)
        return design.new_block()

    for t_subset in design.all_t_subsets:
        if design.coverage[t_subset]:
            continue

        simulated_size = len(open_block.elements.union(t_subset))
        if simulated_size > design.k:
            open_block = add_open_block_to_design()
            open_block.add_t_subset(t_subset, design.t)
        elif simulated_size == design.k:
            open_block.add_t_subset(t_subset, design.t)
            open_block = add_open_block_to_design()
        else:
            open_block.add_t_subset(t_subset, design.t)

    add_open_block_to_design()
    return design


@dataclass(frozen=True, slots=True)
class _TabuListItem:
    block_identifier: int
    element: int


@dataclass(frozen=True, slots=True)
class _Candidate:
    block: _Block
    swapped_out_element: int
    swapped_in_element: int
    conflicts: int
    delta: int

    @property
    def tabu_in(self) -> _TabuListItem:
        return _TabuListItem(self.block.identifier, self.swapped_in_element)

    @property
    def tabu_out(self) -> _TabuListItem:
        return _TabuListItem(self.block.identifier, self.swapped_out_element)


def _calculate_delta_conflict_value(
    design: _CoveringDesign, block: _Block, outgoing: int, incoming: int
) -> int:
    """Return donor delta: newly uncovered subsets minus newly covered subsets."""

    delta = 0
    for subset in sorted(block.covered_t_subsets):
        if outgoing not in subset:
            continue
        if design.coverage_count(subset) == 1:
            delta += 1

        new_subset = tuple(
            sorted((*((element for element in subset if element != outgoing)), incoming))
        )
        if design.coverage_count(new_subset) == 0:
            delta -= 1
    return delta


def _calculate_objective_value(
    _block: _Block, _outgoing: int, _incoming: int, *, _diversification: bool = False
) -> int:
    """The donor's active secondary objective is zero."""

    return 0


class _TabuSearch7:
    """Stateful, bounded translation of the donor strategy's core loop."""

    def __init__(self, design: _CoveringDesign, search_rng: random.Random) -> None:
        self.design = design
        self.search_rng = search_rng

        self.tabu_length_min = (design.v - design.k) // design.k + 1
        self.tabu_length = (
            search_rng.randrange(7 * self.tabu_length_min) + self.tabu_length_min
        )
        initial_block_count = len(design.blocks)
        self.initial_block_count = initial_block_count
        self.tabu_iterations = int(
            initial_block_count
            * (2 + (1 / float(design.t)))
            * math.pow(initial_block_count, 0.6)
        )

        self.tabu_list_in: list[_TabuListItem] = []
        self.tabu_list_out: list[_TabuListItem] = []
        self.non_removable_blocks: set[int] = set()
        self.count = 0
        self.lowest_conflicts = 0
        self.diversification = False
        self.solution: BlockSnapshot = ()
        self.best_situation: BlockSnapshot = ()

    def save_solution_and_remove_block(self) -> None:
        self.solution = _snapshot_blocks(self.design.blocks)
        self.remove_block()
        self.clear_tabu_lists()
        if not self.diversification:
            self.reset_element_frequency()
        self.better_situation_found()

    def better_situation_found(self) -> None:
        self.count = 0
        self.lowest_conflicts = self.design.conflict_count()
        self.best_situation = _snapshot_blocks(self.design.blocks)

    def clear_tabu_lists(self) -> None:
        self.tabu_list_in.clear()
        self.tabu_list_out.clear()

    def reset_element_frequency(self) -> None:
        # The donor's frequency objective is inactive in TabuSearch7.  Keep
        # the lifecycle call to preserve the source control flow explicitly.
        return

    def increment_element_frequency(self) -> None:
        # The donor's frequency objective is inactive in TabuSearch7.
        return

    def remove_block(self) -> _Block:
        max_damage = -1
        blocks_to_remove: list[_Block] = []

        eligible_blocks = [
            block
            for block in self.design.blocks
            if block.identifier not in self.non_removable_blocks
        ]
        if not eligible_blocks:
            eligible_blocks = list(self.design.blocks)

        # `max_damage` and the strict `<` comparison intentionally retain the
        # donor's minimum-damage rule despite the source variable's name.
        for block in eligible_blocks:
            damage = self._calculate_delta_conflict_value_for_removal(block)
            if damage == 0:
                blocks_to_remove.clear()
                blocks_to_remove.append(block)
                break
            if damage < max_damage or max_damage == -1:
                max_damage = damage
                blocks_to_remove.clear()
                blocks_to_remove.append(block)
                self.non_removable_blocks.add(block.identifier)
            elif damage == max_damage:
                blocks_to_remove.append(block)
                self.non_removable_blocks.add(block.identifier)

        if not blocks_to_remove:
            raise RuntimeError("cannot remove a block from an empty design")
        selected = blocks_to_remove[self.search_rng.randrange(len(blocks_to_remove))]
        self.design.remove_block(selected)
        return selected

    def _calculate_delta_conflict_value_for_removal(self, block: _Block) -> int:
        return sum(
            self.design.coverage_count(subset) == 1
            for subset in sorted(block.covered_t_subsets)
        )

    def generate_candidates(self) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        current_conflicts = self.design.conflict_count()
        incoming_union: set[int] = set()
        for subset in sorted(self.design.uncovered_t_subsets):
            incoming_union.update(subset)

        # The list order is the explicit canonical block traversal used by
        # this port; it does not claim to reproduce Java HashSet order.
        for block in self.design.blocks:
            incoming_elements = sorted(incoming_union.difference(block.elements))
            for outgoing in sorted(block.elements):
                for incoming in incoming_elements:
                    predicted_conflicts = current_conflicts + _calculate_delta_conflict_value(
                        self.design, block, outgoing, incoming
                    )
                    objective_delta = _calculate_objective_value(block, outgoing, incoming)
                    candidates.append(
                        _Candidate(
                            block,
                            outgoing,
                            incoming,
                            predicted_conflicts,
                            predicted_conflicts + objective_delta,
                        )
                    )
                    # This is the donor's labeled outer-loop break: only the
                    # canonical prefix through the first zero is retained.
                    if predicted_conflicts == 0:
                        return candidates
        return candidates

    def is_tabu(self, candidate: _Candidate) -> bool:
        # Directionality is donor-parity: incoming matches prior tabu-out OR
        # outgoing matches prior tabu-in, and only within the same block.
        return candidate.tabu_in in self.tabu_list_out or candidate.tabu_out in self.tabu_list_in

    def get_best_candidate(self, candidates: Iterable[_Candidate]) -> _Candidate | None:
        best_candidates: list[_Candidate] = []
        best_delta = -1
        best_conflicts = -1

        for candidate in candidates:
            if best_delta == -1 and not self.is_tabu(candidate):
                best_candidates.append(candidate)
                best_delta = candidate.delta
                best_conflicts = candidate.conflicts

            # The donor's aspiration check intentionally precedes tabu
            # filtering: a zero-conflict candidate is accepted even if tabu.
            if candidate.conflicts == 0:
                best_candidates.clear()
                best_candidates.append(candidate)
                break
            elif (
                candidate.conflicts == best_conflicts
                and candidate.delta == best_delta
                and not self.is_tabu(candidate)
            ):
                best_candidates.append(candidate)
            elif (
                candidate.conflicts == best_conflicts
                and candidate.delta < best_delta
                and not self.is_tabu(candidate)
            ):
                best_candidates.clear()
                best_candidates.append(candidate)
                best_delta = candidate.delta
            elif candidate.conflicts < best_conflicts and not self.is_tabu(candidate):
                best_candidates.clear()
                best_candidates.append(candidate)
                best_delta = candidate.delta
                best_conflicts = candidate.conflicts

        if not best_candidates:
            return None
        if len(best_candidates) == 1:
            return best_candidates[0]
        return best_candidates[self.search_rng.randrange(len(best_candidates))]

    def execute_candidate(self, candidate: _Candidate) -> None:
        self.design.replace_element(
            candidate.block, candidate.swapped_out_element, candidate.swapped_in_element
        )
        self.tabu_list_in.append(candidate.tabu_in)
        if self.tabu_list_in.count(candidate.tabu_in) > 1:
            self.tabu_list_in.pop()
        self.tabu_list_out.append(candidate.tabu_out)
        if self.tabu_list_out.count(candidate.tabu_out) > 1:
            self.tabu_list_out.pop()
        self.adjust_tabu_list()
        self.increment_element_frequency()

    def adjust_tabu_list(self) -> None:
        tabu_length = max(2, int(self.tabu_length + math.pow(0.25 * self.count, 0.65)))
        random_length = self.search_rng.randrange(tabu_length // 2)
        while len(self.tabu_list_in) > random_length:
            self.tabu_list_in.pop(0)

        random_length = self.search_rng.randrange(tabu_length)
        while len(self.tabu_list_out) > random_length:
            self.tabu_list_out.pop(0)

    def perturbation_block_candidates(self) -> list[_Block]:
        blocks: list[_Block] = []
        value = -1
        for block in self.design.blocks:
            score = sum(
                self.design.coverage_count(subset)
                for subset in sorted(block.covered_t_subsets)
            )
            if value == -1 or score > value:
                value = score
                blocks.clear()
                blocks.append(block)
            elif len(block.covered_t_subsets) == value:
                # Characterized donor tie-condition bug: the source compares
                # covered-subset cardinality to `value` (the score), rather
                # than comparing this block's score to the current maximum.
                blocks.append(block)
        return blocks

    def perturbate(self) -> None:
        blocks = self.perturbation_block_candidates()
        if not blocks:
            raise RuntimeError("cannot perturb an empty design")
        block_to_perturbate = blocks[self.search_rng.randrange(len(blocks))]
        original_elements = tuple(sorted(block_to_perturbate.elements))

        for outgoing in original_elements:
            if self.design.conflict_count() == 0:
                break
            outside_elements = sorted(
                set(range(self.design.v)).difference(block_to_perturbate.elements)
            )
            candidate_to_execute: _Candidate | None = None
            for incoming in outside_elements:
                conflict_delta = _calculate_delta_conflict_value(
                    self.design, block_to_perturbate, outgoing, incoming
                )
                if (
                    candidate_to_execute is None
                    or candidate_to_execute.conflicts > conflict_delta
                    or (
                        candidate_to_execute.conflicts == conflict_delta
                        and bool(self.search_rng.getrandbits(1))
                    )
                ):
                    candidate_to_execute = _Candidate(
                        block_to_perturbate,
                        outgoing,
                        incoming,
                        conflict_delta,
                        conflict_delta,
                    )
            if candidate_to_execute is not None:
                self.execute_candidate(candidate_to_execute)

    def check_diversification(self) -> None:
        if (
            self.count > 0
            and self.count % (2 * self.tabu_iterations) == 0
            and not self.diversification
        ):
            self.perturbate()
            self.reset_element_frequency()

    def tabu_search(self) -> None:
        if self.design.conflict_count() == 0:
            return

        if self.count == 1 and self.non_removable_blocks:
            self.non_removable_blocks.clear()

        candidates = self.generate_candidates()
        best_candidate = self.get_best_candidate(candidates)
        if best_candidate is None:
            self.clear_tabu_lists()
            self.perturbate()
        else:
            self.execute_candidate(best_candidate)

    def run_one_iteration(self) -> None:
        self.count += 1
        self.check_diversification()
        self.tabu_search()

        current_conflicts = self.design.conflict_count()
        if current_conflicts < self.lowest_conflicts and current_conflicts != 0:
            self.better_situation_found()

        if current_conflicts == 0:
            self.save_solution_and_remove_block()


def _validate_run_inputs(v: int, k: int, t: int, config: TabuSearch7RunConfig) -> None:
    _require_integer("v", v)
    _require_integer("k", k)
    _require_integer("t", t)
    if not v > k > t >= 2:
        raise ValueError("configuration requires v > k > t >= 2")
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")


def run_covering_design_tabu7(
    v: int,
    k: int,
    t: int,
    *,
    config: TabuSearch7RunConfig,
) -> TabuSearch7Result:
    """Run the bounded research-only TabuSearch7 covering-design port.

    The constructor and search PRNGs are isolated.  The only normal
    termination condition is the caller-owned iteration limit, reported as
    ``ITERATION_LIMIT``.  ``best_complete_blocks`` is the last complete
    covering saved before the monotonic deletion step; ``final_blocks`` and
    ``final_conflicts`` describe the possibly incomplete state at cutoff.
    """

    _validate_run_inputs(v, k, t, config)

    design = _construct_initial_design(v, k, t, random.Random(config.constructor_seed))
    search = _TabuSearch7(design, random.Random(config.search_seed))

    # Donor initialization: save the complete construction, remove exactly
    # one block, clear tabu state, and reset the better-situation counters.
    search.save_solution_and_remove_block()
    for _ in range(config.max_iterations):
        search.run_one_iteration()

    return TabuSearch7Result(
        best_complete_blocks=search.solution,
        final_blocks=_snapshot_blocks(design.blocks),
        final_conflicts=design.conflict_count(),
        iterations=config.max_iterations,
        termination_reason="ITERATION_LIMIT",
    )


__all__ = [
    "TabuSearch7Result",
    "TabuSearch7RunConfig",
    "run_covering_design_tabu7",
]
