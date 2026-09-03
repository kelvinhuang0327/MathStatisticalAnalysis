"""Deterministic exhaustive exact radius-two portfolio local escape.

The neighborhood is exactly the set of canonical portfolios reachable by two
legal one-number ticket exchanges.  Intermediate portfolios are never scored
or filtered.  Endpoints are decomposed by their symmetric difference from the
input portfolio:

* one original ticket is replaced by a ticket at Johnson-graph distance one
  or two; or
* two original tickets are each replaced by a one-exchange neighbor.

Those cases are disjoint and complete.  The second case explicitly removes
the duplicate orientation when both replacements can be assigned to either
original ticket.

Every endpoint is scored against the unchanged exact M3+ objective.  Winning
draws are enumerated once and represented as packed Python integers.  For a
fixed set of unchanged tickets, exact endpoint coverage is

``covered_by_unchanged + popcount(candidate_union & uncovered_by_unchanged)``.

No sampling, floating point, random state, or objective approximation is used.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from lottolab.research.reference_e_exact_one_exchange_refinement import (
    Portfolio,
    Ticket,
    canonicalize_portfolio,
)

type ProgressCallback = Callable[[str], None]
type IterationCompletedCallback = Callable[[ExactRadiusTwoIteration], None]


@dataclass(frozen=True, slots=True)
class RadiusTwoEndpointFeasibility:
    """Exact structural cardinality of one radius-two neighborhood."""

    input_portfolio: Portfolio
    first_level_neighbor_count: int
    single_replacement_endpoint_count: int
    two_replacement_endpoint_count: int
    unique_endpoint_count: int


@dataclass(frozen=True, slots=True)
class ExactRadiusTwoIteration:
    """One accepted or terminal complete radius-two evaluation."""

    iteration_index: int
    input_portfolio: Portfolio
    input_q: Fraction
    first_level_neighbor_count: int
    single_replacement_endpoint_count: int
    two_replacement_endpoint_count: int
    unique_endpoint_count: int
    best_endpoint_portfolio: Portfolio
    best_endpoint_q: Fraction
    delta: Fraction
    accepted_move: bool


@dataclass(frozen=True, slots=True)
class ExactRadiusTwoAscentResult:
    """Strict best-improvement radius-two ascent through exact local optimality."""

    seed_portfolio: Portfolio
    seed_q: Fraction
    iterations: tuple[ExactRadiusTwoIteration, ...]
    move_count: int
    unique_endpoints_evaluated: int
    terminal_portfolio: Portfolio
    terminal_q: Fraction


@dataclass(frozen=True, slots=True)
class PackedWinningSpace:
    """Complete winning space represented by one packed bitset per number."""

    pool_size: int
    draw_size: int
    total_draws: int
    universe_mask: int
    number_draw_bitsets: tuple[int, ...]

    @classmethod
    def build(cls, pool_size: int, draw_size: int) -> PackedWinningSpace:
        if not 1 <= draw_size <= pool_size <= 64:
            raise ValueError("require 1 <= draw_size <= pool_size <= 64")

        total_draws = math.comb(pool_size, draw_size)
        byte_count = (total_draws + 7) // 8
        buffers = [bytearray(byte_count) for _ in range(pool_size)]
        for draw_index, draw in enumerate(
            itertools.combinations(range(1, pool_size + 1), draw_size)
        ):
            byte_index = draw_index >> 3
            draw_bit = 1 << (draw_index & 7)
            for number in draw:
                buffers[number - 1][byte_index] |= draw_bit

        number_draw_bitsets = tuple(int.from_bytes(buffer, "little") for buffer in buffers)
        return cls(
            pool_size=pool_size,
            draw_size=draw_size,
            total_draws=total_draws,
            universe_mask=(1 << total_draws) - 1,
            number_draw_bitsets=number_draw_bitsets,
        )

    def restricted_number_bitsets(self, domain: int) -> tuple[int, ...]:
        """Return every number-incidence bitset restricted to ``domain``."""

        if domain & ~self.universe_mask:
            raise ValueError("domain contains bits outside the winning space")
        return tuple(bitset & domain for bitset in self.number_draw_bitsets)

    def ticket_qualification_bitset(
        self,
        ticket: Ticket,
        *,
        restricted_number_bitsets: tuple[int, ...] | None = None,
    ) -> int:
        """Return exact M3+ qualifying draws for ``ticket`` in a domain.

        The descending dynamic program stores draws containing at least one,
        two, and three processed ticket numbers.  It is Boolean algebra over
        complete draw-incidence bitsets, so the returned set is exact.
        """

        _validate_ticket(ticket, pool_size=self.pool_size, draw_size=self.draw_size)
        number_bitsets = (
            self.number_draw_bitsets
            if restricted_number_bitsets is None
            else restricted_number_bitsets
        )
        if len(number_bitsets) != self.pool_size:
            raise ValueError("restricted number-bitset count does not match pool_size")

        at_least_one = 0
        at_least_two = 0
        at_least_three = 0
        for number in ticket:
            containing_number = number_bitsets[number - 1]
            at_least_three |= at_least_two & containing_number
            at_least_two |= at_least_one & containing_number
            at_least_one |= containing_number
        return at_least_three

    def exact_portfolio_q(self, portfolio: Portfolio) -> Fraction:
        """Return the unchanged exact M3+ portfolio objective."""

        canonical = _validate_and_canonicalize_portfolio(
            portfolio,
            pool_size=self.pool_size,
            draw_size=self.draw_size,
        )
        covered = 0
        for ticket in canonical:
            covered |= self.ticket_qualification_bitset(ticket)
        return Fraction(covered.bit_count(), self.total_draws)


def _validate_ticket(ticket: Ticket, *, pool_size: int, draw_size: int) -> None:
    if len(ticket) != draw_size or len(set(ticket)) != draw_size:
        raise ValueError(f"ticket must contain exactly {draw_size} distinct numbers")
    if ticket != tuple(sorted(ticket)):
        raise ValueError("ticket must use ascending canonical order")
    if any(number < 1 or number > pool_size for number in ticket):
        raise ValueError(f"ticket number outside 1..{pool_size}")


def _validate_and_canonicalize_portfolio(
    portfolio: Portfolio,
    *,
    pool_size: int,
    draw_size: int,
) -> Portfolio:
    canonical = canonicalize_portfolio(portfolio)
    if not canonical:
        raise ValueError("portfolio must contain at least one ticket")
    if len(canonical) != len(portfolio):
        raise ValueError("portfolio must contain unique tickets")
    for ticket in canonical:
        _validate_ticket(ticket, pool_size=pool_size, draw_size=draw_size)
    return canonical


def _one_exchange_tickets(ticket: Ticket, pool_size: int) -> tuple[Ticket, ...]:
    ticket_numbers = set(ticket)
    candidates = {
        tuple(sorted((ticket_numbers - {removed}) | {added}))
        for removed in ticket
        for added in range(1, pool_size + 1)
        if added not in ticket_numbers
    }
    return tuple(sorted(candidates))


def one_exchange_candidates_by_slot(
    portfolio: Portfolio,
    pool_size: int,
) -> tuple[tuple[Ticket, ...], ...]:
    """Return every legal first-level replacement ticket by original slot."""

    portfolio_set = set(portfolio)
    return tuple(
        tuple(
            candidate
            for candidate in _one_exchange_tickets(ticket, pool_size)
            if candidate not in portfolio_set
        )
        for ticket in portfolio
    )


def _single_replacement_tickets(
    ticket: Ticket,
    *,
    pool_size: int,
    portfolio_set: set[Ticket],
) -> tuple[Ticket, ...]:
    """Return all endpoints replacing only ``ticket`` after exactly two moves.

    A two-step path in the ticket Johnson graph can end at distance one or two.
    If a common intermediate is another portfolio ticket, performing that
    ticket's move first and then moving ``ticket`` into the vacated identity is
    legal and reaches the same canonical endpoint.  Therefore every distance
    one/two ticket outside the portfolio is reachable and no other ticket is.
    """

    ticket_numbers = set(ticket)
    outside = tuple(number for number in range(1, pool_size + 1) if number not in ticket_numbers)
    candidates = set(_one_exchange_tickets(ticket, pool_size))
    for removed_pair in itertools.combinations(ticket, 2):
        retained = ticket_numbers - set(removed_pair)
        for added_pair in itertools.combinations(outside, 2):
            candidates.add(tuple(sorted((*retained, *added_pair))))
    candidates.difference_update(portfolio_set)
    return tuple(sorted(candidates))


def radius_two_endpoint_feasibility(
    pool_size: int,
    draw_size: int,
    portfolio: Portfolio,
) -> RadiusTwoEndpointFeasibility:
    """Return the exact canonical radius-two endpoint cardinality."""

    canonical = _validate_and_canonicalize_portfolio(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
    )
    portfolio_set = set(canonical)
    first_level_by_slot = one_exchange_candidates_by_slot(canonical, pool_size)
    first_level_neighbor_count = sum(len(candidates) for candidates in first_level_by_slot)
    single_replacement_endpoint_count = sum(
        len(
            _single_replacement_tickets(
                ticket,
                pool_size=pool_size,
                portfolio_set=portfolio_set,
            )
        )
        for ticket in canonical
    )

    two_replacement_endpoint_count = 0
    for left_candidates, right_candidates in itertools.combinations(first_level_by_slot, 2):
        left_set = set(left_candidates)
        right_set = set(right_candidates)
        intersection_count = len(left_set & right_set)
        two_replacement_endpoint_count += (
            len(left_candidates) * len(right_candidates)
            - intersection_count
            - math.comb(intersection_count, 2)
        )

    return RadiusTwoEndpointFeasibility(
        input_portfolio=canonical,
        first_level_neighbor_count=first_level_neighbor_count,
        single_replacement_endpoint_count=single_replacement_endpoint_count,
        two_replacement_endpoint_count=two_replacement_endpoint_count,
        unique_endpoint_count=(single_replacement_endpoint_count + two_replacement_endpoint_count),
    )


def _portfolio_with_one_replacement(
    portfolio: Portfolio,
    slot_index: int,
    candidate: Ticket,
) -> Portfolio:
    return tuple(sorted((*portfolio[:slot_index], *portfolio[slot_index + 1 :], candidate)))


def _portfolio_with_two_replacements(
    portfolio: Portfolio,
    left_slot: int,
    right_slot: int,
    left_candidate: Ticket,
    right_candidate: Ticket,
) -> Portfolio:
    retained = tuple(
        ticket
        for slot_index, ticket in enumerate(portfolio)
        if slot_index not in (left_slot, right_slot)
    )
    return tuple(sorted((*retained, left_candidate, right_candidate)))


def evaluate_exact_radius_two_neighborhood(
    space: PackedWinningSpace,
    portfolio: Portfolio,
    *,
    progress: ProgressCallback | None = None,
) -> ExactRadiusTwoIteration:
    """Exact-score every unique canonical endpoint reachable in two moves."""

    canonical = _validate_and_canonicalize_portfolio(
        portfolio,
        pool_size=space.pool_size,
        draw_size=space.draw_size,
    )
    feasibility = radius_two_endpoint_feasibility(
        space.pool_size,
        space.draw_size,
        canonical,
    )
    portfolio_set = set(canonical)
    first_level_by_slot = one_exchange_candidates_by_slot(canonical, space.pool_size)
    original_qualification = tuple(
        space.ticket_qualification_bitset(ticket) for ticket in canonical
    )
    input_covered = 0
    for bitset in original_qualification:
        input_covered |= bitset
    input_count = input_covered.bit_count()

    best_count = -1
    best_portfolio: Portfolio | None = None
    single_evaluated = 0
    two_evaluated = 0

    for slot_index, ticket in enumerate(canonical):
        unchanged_covered = 0
        for other_slot, bitset in enumerate(original_qualification):
            if other_slot != slot_index:
                unchanged_covered |= bitset
        domain = space.universe_mask ^ unchanged_covered
        base_count = space.total_draws - domain.bit_count()
        restricted_numbers = space.restricted_number_bitsets(domain)
        candidates = _single_replacement_tickets(
            ticket,
            pool_size=space.pool_size,
            portfolio_set=portfolio_set,
        )
        for candidate in candidates:
            candidate_bits = space.ticket_qualification_bitset(
                candidate,
                restricted_number_bitsets=restricted_numbers,
            )
            candidate_count = base_count + candidate_bits.bit_count()
            single_evaluated += 1
            if candidate_count >= best_count:
                endpoint = _portfolio_with_one_replacement(
                    canonical,
                    slot_index,
                    candidate,
                )
                if (
                    candidate_count > best_count
                    or best_portfolio is None
                    or endpoint < best_portfolio
                ):
                    best_count = candidate_count
                    best_portfolio = endpoint
        if progress is not None:
            progress(f"single slot={slot_index + 1}/{len(canonical)} evaluated={single_evaluated}")

    slot_pairs = tuple(itertools.combinations(range(len(canonical)), 2))
    for pair_index, (left_slot, right_slot) in enumerate(slot_pairs, start=1):
        unchanged_covered = 0
        for other_slot, bitset in enumerate(original_qualification):
            if other_slot not in (left_slot, right_slot):
                unchanged_covered |= bitset
        domain = space.universe_mask ^ unchanged_covered
        base_count = space.total_draws - domain.bit_count()
        restricted_numbers = space.restricted_number_bitsets(domain)

        left_candidates = first_level_by_slot[left_slot]
        right_candidates = first_level_by_slot[right_slot]
        left_scored = tuple(
            (
                candidate,
                candidate_bits,
                candidate_bits.bit_count(),
            )
            for candidate in left_candidates
            for candidate_bits in (
                space.ticket_qualification_bitset(
                    candidate,
                    restricted_number_bitsets=restricted_numbers,
                ),
            )
        )
        right_scored = tuple(
            (
                candidate,
                candidate_bits,
                candidate_bits.bit_count(),
            )
            for candidate in right_candidates
            for candidate_bits in (
                space.ticket_qualification_bitset(
                    candidate,
                    restricted_number_bitsets=restricted_numbers,
                ),
            )
        )

        overlap = set(left_candidates) & set(right_candidates)
        if not overlap:
            for left_candidate, left_bits, left_count in left_scored:
                for right_candidate, right_bits, right_count in right_scored:
                    candidate_count = (
                        base_count + left_count + right_count - (left_bits & right_bits).bit_count()
                    )
                    two_evaluated += 1
                    if candidate_count >= best_count:
                        endpoint = _portfolio_with_two_replacements(
                            canonical,
                            left_slot,
                            right_slot,
                            left_candidate,
                            right_candidate,
                        )
                        if (
                            candidate_count > best_count
                            or best_portfolio is None
                            or endpoint < best_portfolio
                        ):
                            best_count = candidate_count
                            best_portfolio = endpoint
        else:
            left_set = set(left_candidates)
            right_set = set(right_candidates)
            for left_candidate, left_bits, left_count in left_scored:
                for right_candidate, right_bits, right_count in right_scored:
                    if left_candidate == right_candidate:
                        continue
                    duplicate_reverse_orientation = (
                        right_candidate in left_set
                        and left_candidate in right_set
                        and right_candidate < left_candidate
                    )
                    if duplicate_reverse_orientation:
                        continue
                    candidate_count = (
                        base_count + left_count + right_count - (left_bits & right_bits).bit_count()
                    )
                    two_evaluated += 1
                    if candidate_count >= best_count:
                        endpoint = _portfolio_with_two_replacements(
                            canonical,
                            left_slot,
                            right_slot,
                            left_candidate,
                            right_candidate,
                        )
                        if (
                            candidate_count > best_count
                            or best_portfolio is None
                            or endpoint < best_portfolio
                        ):
                            best_count = candidate_count
                            best_portfolio = endpoint

        if progress is not None:
            progress(
                f"pair={pair_index}/{len(slot_pairs)} slots={left_slot},{right_slot} "
                f"evaluated={two_evaluated}"
            )

    if single_evaluated != feasibility.single_replacement_endpoint_count:
        raise RuntimeError(
            "single-replacement endpoint count mismatch: "
            f"expected {feasibility.single_replacement_endpoint_count}, "
            f"got {single_evaluated}"
        )
    if two_evaluated != feasibility.two_replacement_endpoint_count:
        raise RuntimeError(
            "two-replacement endpoint count mismatch: "
            f"expected {feasibility.two_replacement_endpoint_count}, got {two_evaluated}"
        )
    if best_portfolio is None or best_count < 0:
        raise RuntimeError("radius-two neighborhood unexpectedly has no endpoint")

    input_q = Fraction(input_count, space.total_draws)
    best_q = Fraction(best_count, space.total_draws)
    return ExactRadiusTwoIteration(
        iteration_index=0,
        input_portfolio=canonical,
        input_q=input_q,
        first_level_neighbor_count=feasibility.first_level_neighbor_count,
        single_replacement_endpoint_count=single_evaluated,
        two_replacement_endpoint_count=two_evaluated,
        unique_endpoint_count=single_evaluated + two_evaluated,
        best_endpoint_portfolio=best_portfolio,
        best_endpoint_q=best_q,
        delta=best_q - input_q,
        accepted_move=best_count > input_count,
    )


def iterative_exact_radius_two_ascent(
    space: PackedWinningSpace,
    seed_portfolio: Portfolio,
    *,
    progress: ProgressCallback | None = None,
    resume_iterations: tuple[ExactRadiusTwoIteration, ...] = (),
    iteration_completed: IterationCompletedCallback | None = None,
) -> ExactRadiusTwoAscentResult:
    """Repeat strict deterministic best radius-two moves to local optimality.

    ``resume_iterations`` must be a contiguous prefix previously emitted by
    this exact method.  Its structural counts, portfolios, and exact objective
    values are replay-validated before any new neighborhood is evaluated.
    ``iteration_completed`` runs only after a newly completed exhaustive
    iteration has been appended, allowing callers to persist an atomic
    checkpoint without changing the mathematical result.
    """

    seed = _validate_and_canonicalize_portfolio(
        seed_portfolio,
        pool_size=space.pool_size,
        draw_size=space.draw_size,
    )
    current = seed
    iterations: list[ExactRadiusTwoIteration] = list(resume_iterations)
    move_count = 0
    unique_endpoints_evaluated = 0

    for expected_index, iteration in enumerate(iterations):
        if iteration.iteration_index != expected_index:
            raise ValueError("resume iteration index is not contiguous")
        if iteration.input_portfolio != current:
            raise ValueError("resume iteration portfolio continuity mismatch")
        if iteration.input_q != space.exact_portfolio_q(iteration.input_portfolio):
            raise ValueError("resume iteration input exact-Q replay mismatch")
        if iteration.best_endpoint_portfolio == iteration.input_portfolio:
            raise ValueError("resume iteration endpoint must differ from its input")
        if iteration.best_endpoint_q != space.exact_portfolio_q(iteration.best_endpoint_portfolio):
            raise ValueError("resume iteration best exact-Q replay mismatch")
        if iteration.delta != iteration.best_endpoint_q - iteration.input_q:
            raise ValueError("resume iteration delta mismatch")
        if iteration.accepted_move is not (iteration.best_endpoint_q > iteration.input_q):
            raise ValueError("resume iteration strict-acceptance mismatch")
        feasibility = radius_two_endpoint_feasibility(
            space.pool_size,
            space.draw_size,
            iteration.input_portfolio,
        )
        observed_counts = (
            iteration.first_level_neighbor_count,
            iteration.single_replacement_endpoint_count,
            iteration.two_replacement_endpoint_count,
            iteration.unique_endpoint_count,
        )
        expected_counts = (
            feasibility.first_level_neighbor_count,
            feasibility.single_replacement_endpoint_count,
            feasibility.two_replacement_endpoint_count,
            feasibility.unique_endpoint_count,
        )
        if observed_counts != expected_counts:
            raise ValueError("resume iteration endpoint cardinality mismatch")
        unique_endpoints_evaluated += iteration.unique_endpoint_count
        if not iteration.accepted_move:
            if expected_index != len(iterations) - 1:
                raise ValueError("resume trace continues after a terminal iteration")
            return ExactRadiusTwoAscentResult(
                seed_portfolio=seed,
                seed_q=iterations[0].input_q,
                iterations=tuple(iterations),
                move_count=move_count,
                unique_endpoints_evaluated=unique_endpoints_evaluated,
                terminal_portfolio=current,
                terminal_q=iteration.input_q,
            )
        current = iteration.best_endpoint_portfolio
        move_count += 1

    while True:
        evaluated = evaluate_exact_radius_two_neighborhood(
            space,
            current,
            progress=progress,
        )
        iteration = ExactRadiusTwoIteration(
            iteration_index=len(iterations),
            input_portfolio=evaluated.input_portfolio,
            input_q=evaluated.input_q,
            first_level_neighbor_count=evaluated.first_level_neighbor_count,
            single_replacement_endpoint_count=(evaluated.single_replacement_endpoint_count),
            two_replacement_endpoint_count=evaluated.two_replacement_endpoint_count,
            unique_endpoint_count=evaluated.unique_endpoint_count,
            best_endpoint_portfolio=evaluated.best_endpoint_portfolio,
            best_endpoint_q=evaluated.best_endpoint_q,
            delta=evaluated.delta,
            accepted_move=evaluated.accepted_move,
        )
        iterations.append(iteration)
        unique_endpoints_evaluated += iteration.unique_endpoint_count
        if iteration_completed is not None:
            iteration_completed(iteration)
        if not iteration.accepted_move:
            return ExactRadiusTwoAscentResult(
                seed_portfolio=seed,
                seed_q=iterations[0].input_q,
                iterations=tuple(iterations),
                move_count=move_count,
                unique_endpoints_evaluated=unique_endpoints_evaluated,
                terminal_portfolio=current,
                terminal_q=iteration.input_q,
            )

        current = iteration.best_endpoint_portfolio
        move_count += 1
