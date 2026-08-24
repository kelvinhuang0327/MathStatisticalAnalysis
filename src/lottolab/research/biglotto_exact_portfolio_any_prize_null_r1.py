"""Exact portfolio-level Big Lotto ``ANY_PRIZE`` null probability.

The official outcome is a six-number main set plus one distinct special
number.  For any ticket, the canonical prize evaluator declares a win exactly
when the ticket contains at least three numbers from the outcome's unordered
seven-number union: three main hits win directly, while two main hits win only
when the third ticket number is the special number.  The designation of which
of the seven numbers is special therefore does not change ``ANY_PRIZE``.

This module counts the exact dependent portfolio union on those seven-number
sets.  Its complement is the family of seven-sets containing no three-number
subset from any ticket.  Pair-completion bitmasks reject such ticket triples,
and an increasing five-number prefix counts its final two choices exactly.
Every seven-set is considered once; no Monte Carlo, empirical frequency, or
ticket-independence approximation is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Final

BIG_LOTTO_POOL_SIZE: Final = 49
BIG_LOTTO_TICKET_SIZE: Final = 6
OFFICIAL_OUTCOME_MAIN_SIZE: Final = 6
OFFICIAL_OUTCOME_UNION_SIZE: Final = 7
SPECIAL_DESIGNATIONS_PER_UNION: Final = 7
TOTAL_SEVEN_SET_COUNT: Final = comb(BIG_LOTTO_POOL_SIZE, OFFICIAL_OUTCOME_UNION_SIZE)
TOTAL_OUTCOME_COUNT: Final = (
    comb(BIG_LOTTO_POOL_SIZE, OFFICIAL_OUTCOME_MAIN_SIZE)
    * (BIG_LOTTO_POOL_SIZE - OFFICIAL_OUTCOME_MAIN_SIZE)
)

if TOTAL_OUTCOME_COUNT != 601_304_088:
    raise ArithmeticError("official Big Lotto outcome-space identity changed")
if TOTAL_OUTCOME_COUNT != TOTAL_SEVEN_SET_COUNT * SPECIAL_DESIGNATIONS_PER_UNION:
    raise ArithmeticError("seven-set outcome-space reduction is inconsistent")

type BigLottoTicket = tuple[int, ...]
type BigLottoPortfolio = tuple[BigLottoTicket, ...]


class BigLottoExactPortfolioNullContractError(ValueError):
    """The supplied portfolio is not a canonical native Big Lotto portfolio."""


@dataclass(frozen=True, slots=True)
class ExactPortfolioAnyPrizeProbability:
    """Integer-exact evidence for one canonical portfolio's null probability."""

    favorable_outcome_count: int
    total_outcome_count: int
    exact_probability: Fraction
    favorable_seven_set_count: int
    total_seven_set_count: int
    input_ticket_count: int
    unique_ticket_count: int

    def __post_init__(self) -> None:
        integer_fields = (
            self.favorable_outcome_count,
            self.total_outcome_count,
            self.favorable_seven_set_count,
            self.total_seven_set_count,
            self.input_ticket_count,
            self.unique_ticket_count,
        )
        if any(type(value) is not int for value in integer_fields):
            raise TypeError("exact portfolio result counts must be built-in integers")
        if not 0 <= self.favorable_outcome_count <= self.total_outcome_count:
            raise ValueError("favorable outcome count is outside the official outcome space")
        if self.total_outcome_count != TOTAL_OUTCOME_COUNT:
            raise ValueError("result denominator is not the official Big Lotto outcome count")
        if not 0 <= self.favorable_seven_set_count <= self.total_seven_set_count:
            raise ValueError("favorable seven-set count is outside its finite space")
        if self.total_seven_set_count != TOTAL_SEVEN_SET_COUNT:
            raise ValueError("result seven-set denominator is inconsistent")
        if self.favorable_outcome_count != (
            self.favorable_seven_set_count * SPECIAL_DESIGNATIONS_PER_UNION
        ):
            raise ValueError("outcome count does not match the seven-set reduction")
        if not 0 <= self.unique_ticket_count <= self.input_ticket_count:
            raise ValueError("ticket-count evidence is inconsistent")
        if type(self.exact_probability) is not Fraction:
            raise TypeError("exact_probability must be a fractions.Fraction")
        expected_probability = Fraction(
            self.favorable_outcome_count,
            self.total_outcome_count,
        )
        if self.exact_probability != expected_probability:
            raise ValueError("exact_probability does not match the integer counts")

    def canonical_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation without making a float authoritative."""

        return {
            "EXACT_PROBABILITY": {
                "DENOMINATOR": self.exact_probability.denominator,
                "NUMERATOR": self.exact_probability.numerator,
            },
            "FAVORABLE_OUTCOME_COUNT": self.favorable_outcome_count,
            "FAVORABLE_SEVEN_SET_COUNT": self.favorable_seven_set_count,
            "INPUT_TICKET_COUNT": self.input_ticket_count,
            "TOTAL_OUTCOME_COUNT": self.total_outcome_count,
            "TOTAL_SEVEN_SET_COUNT": self.total_seven_set_count,
            "UNIQUE_TICKET_COUNT": self.unique_ticket_count,
        }


def _canonicalize_portfolio(portfolio: BigLottoPortfolio) -> BigLottoPortfolio:
    if type(portfolio) is not tuple:
        raise BigLottoExactPortfolioNullContractError("portfolio must be a tuple")

    unique: set[BigLottoTicket] = set()
    for ticket in portfolio:
        if type(ticket) is not tuple:
            raise BigLottoExactPortfolioNullContractError(
                "each ticket must be a canonical tuple"
            )
        if len(ticket) != BIG_LOTTO_TICKET_SIZE:
            raise BigLottoExactPortfolioNullContractError(
                "each ticket must contain exactly 6 numbers"
            )
        if any(type(number) is not int for number in ticket):
            raise BigLottoExactPortfolioNullContractError(
                "ticket numbers must be exact built-in integers"
            )
        if any(not 1 <= number <= BIG_LOTTO_POOL_SIZE for number in ticket):
            raise BigLottoExactPortfolioNullContractError(
                "ticket numbers must be between 1 and 49"
            )
        if len(set(ticket)) != BIG_LOTTO_TICKET_SIZE:
            raise BigLottoExactPortfolioNullContractError(
                "ticket numbers must be distinct"
            )
        if ticket != tuple(sorted(ticket)):
            raise BigLottoExactPortfolioNullContractError(
                "ticket numbers must use canonical ascending order"
            )
        unique.add(ticket)
    return tuple(sorted(unique))


def _triple_completion_masks(
    pool_size: int,
    portfolio: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    """Map each number pair to all third numbers completing a ticket triple."""

    completion = [[0] * pool_size for _ in range(pool_size)]
    for ticket in portfolio:
        zero_based = tuple(number - 1 for number in ticket)
        ticket_mask = 0
        for number in zero_based:
            ticket_mask |= 1 << number
        for left_index, left in enumerate(zero_based):
            left_bit = 1 << left
            for right in zero_based[left_index + 1 :]:
                third_numbers = ticket_mask ^ left_bit ^ (1 << right)
                completion[left][right] |= third_numbers
                completion[right][left] |= third_numbers
    return tuple(tuple(row) for row in completion)


def _count_seven_sets_without_ticket_triple(
    pool_size: int,
    completion: tuple[tuple[int, ...], ...],
) -> int:
    """Count increasing seven-sets avoiding every encoded ticket triple.

    After a valid five-number prefix ``a<b<c<d<e``, ``banned`` contains
    every number that would complete a ticket triple with a prefix pair.
    A sixth number ``x`` is drawn from the remaining allowed mask.  A final
    number ``y`` must additionally avoid completing a triple with ``x`` and
    any one prefix number.  Its valid choices are counted by ``bit_count``;
    there is no seventh-level enumeration.
    """

    if type(pool_size) is not int or pool_size < OFFICIAL_OUTCOME_UNION_SIZE:
        raise ValueError("pool_size must be an integer of at least 7")
    if len(completion) != pool_size or any(len(row) != pool_size for row in completion):
        raise ValueError("completion matrix dimensions do not match pool_size")

    full_mask = (1 << pool_size) - 1
    tail_masks = tuple(
        full_mask ^ ((1 << first_allowed) - 1)
        for first_allowed in range(pool_size + 1)
    )
    valid_seven_sets = 0

    for a in range(pool_size - 6):
        row_a = completion[a]
        for b in range(a + 1, pool_size - 5):
            row_b = completion[b]
            banned_after_b = row_a[b]
            for c in range(b + 1, pool_size - 4):
                if banned_after_b & (1 << c):
                    continue
                row_c = completion[c]
                banned_after_c = banned_after_b | row_a[c] | row_b[c]
                for d in range(c + 1, pool_size - 3):
                    if banned_after_c & (1 << d):
                        continue
                    row_d = completion[d]
                    banned_after_d = (
                        banned_after_c | row_a[d] | row_b[d] | row_c[d]
                    )
                    for e in range(d + 1, pool_size - 2):
                        if banned_after_d & (1 << e):
                            continue
                        row_e = completion[e]
                        banned_after_e = (
                            banned_after_d
                            | row_a[e]
                            | row_b[e]
                            | row_c[e]
                            | row_d[e]
                        )
                        allowed_after_e = tail_masks[e + 1] & ~banned_after_e
                        while allowed_after_e:
                            x_bit = allowed_after_e & -allowed_after_e
                            x = x_bit.bit_length() - 1
                            allowed_after_e ^= x_bit
                            final_conflicts = (
                                row_a[x]
                                | row_b[x]
                                | row_c[x]
                                | row_d[x]
                                | row_e[x]
                            )
                            valid_seven_sets += (
                                allowed_after_e & ~final_conflicts
                            ).bit_count()
    return valid_seven_sets


def exact_seven_set_ticket_triple_union_count(
    pool_size: int,
    portfolio: tuple[tuple[int, ...], ...],
) -> int:
    """Count seven-sets containing at least three numbers from any ticket.

    This generic finite-domain entrypoint exists so independent exhaustive
    tests can exercise the same counter on tractable pools.  The official
    Big Lotto API below fixes the pool and ticket contracts at 49 and 6.
    """

    if type(pool_size) is not int or pool_size < OFFICIAL_OUTCOME_UNION_SIZE:
        raise ValueError("pool_size must be an integer of at least 7")
    if type(portfolio) is not tuple:
        raise ValueError("portfolio must be a tuple")
    for ticket in portfolio:
        if type(ticket) is not tuple or len(ticket) < 3:
            raise ValueError("generic tickets must be tuples containing at least 3 numbers")
        if any(type(number) is not int or not 1 <= number <= pool_size for number in ticket):
            raise ValueError("generic ticket numbers must be integers inside the pool")
        if len(set(ticket)) != len(ticket):
            raise ValueError("generic ticket numbers must be distinct")
    if not portfolio:
        return 0
    completion = _triple_completion_masks(pool_size, portfolio)
    losing_count = _count_seven_sets_without_ticket_triple(pool_size, completion)
    return comb(pool_size, OFFICIAL_OUTCOME_UNION_SIZE) - losing_count


def exact_portfolio_any_prize_probability(
    portfolio: BigLottoPortfolio,
) -> ExactPortfolioAnyPrizeProbability:
    """Return the exact official-null probability that any portfolio ticket wins.

    Exact duplicate tickets are removed before counting and ticket order is
    canonicalized, making duplicate idempotence and portfolio-order invariance
    structural properties of the calculation.
    """

    input_ticket_count = len(portfolio) if type(portfolio) is tuple else 0
    canonical_portfolio = _canonicalize_portfolio(portfolio)
    favorable_seven_sets = exact_seven_set_ticket_triple_union_count(
        BIG_LOTTO_POOL_SIZE,
        canonical_portfolio,
    )
    favorable_outcomes = favorable_seven_sets * SPECIAL_DESIGNATIONS_PER_UNION
    return ExactPortfolioAnyPrizeProbability(
        favorable_outcome_count=favorable_outcomes,
        total_outcome_count=TOTAL_OUTCOME_COUNT,
        exact_probability=Fraction(favorable_outcomes, TOTAL_OUTCOME_COUNT),
        favorable_seven_set_count=favorable_seven_sets,
        total_seven_set_count=TOTAL_SEVEN_SET_COUNT,
        input_ticket_count=input_ticket_count,
        unique_ticket_count=len(canonical_portfolio),
    )
