"""Research-only BIG_LOTTO Fourier(3)+Hot(2) mixed hybrid, five tickets.

Tickets 1-3 are exactly the first three tickets of
:class:`BigLottoFourierChunkK3Adapter`: this adapter calls that adapter's
public ``get_bets`` directly and never recomputes or reimplements Fourier
scoring, ranking, tie-break, or sentinel handling. Tickets 4 and 5 are
consecutive hot-frequency chunks computed fresh from whichever forty-nine
numbers remain after tickets 1-3, using the trailing 100 rows of the same
validated 500-row window (``RECOMPUTED_DOWNSTREAM_MIXED``). This is not the
donor Orthogonal 5-Bet's frozen echo/cold ticket 3 followed by its own hot
ticket 4/5: replacing that donor ticket 3 with a Fourier chunk changes which
numbers are "used", so tickets 4 and 5 are re-ranked against the new
remaining pool rather than reusing, freezing, or patching the donor's
original ticket 4/5 identities.

As in PortfolioBetAdapter, get_bets(history, lottery_type) accepts an
immutable oldest-first tuple of CausalDrawRow. For a target at sequence
index t, callers must supply only rows[:t]: the cutoff is exclusive of the
target and every future draw. We consume rows[max(0, t - 500):t], without
reordering history. There is no target/cutoff argument in this interface, so
excluding target and future rows is the caller's responsibility, not an
inferred date/ID filter.

``CausalDrawRow.numbers`` carries only main numbers by design (see
``base.validated_history``), so counting it directly for hot frequency
already excludes any special/second-zone number.

This identity is not registered in the production catalog and carries no
performance evidence.
"""

from __future__ import annotations

from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_fourier_chunk_k import BigLottoFourierChunkK3Adapter

_STRATEGY_ID = "research_biglotto__fourier3_hot2_k5"
_HISTORY_WINDOW = 500
_FREQUENCY_WINDOW = 100
_PICK_COUNT = 6
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_FOURIER_TICKET_COUNT = 3
_NATIVE_TICKET_COUNT = 5


def _hot_tail_tickets(
    history: tuple[CausalDrawRow, ...],
    used: frozenset[int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Rank the numbers left after `used` by trailing-100 hot frequency.

    Ties break by ascending number, matching the donor's own stable-sort
    behavior over an already-ascending candidate list.
    """

    remaining = [number for number in range(_MIN_NUMBER, _MAX_NUMBER + 1) if number not in used]
    frequencies = Counter(number for row in history[-_FREQUENCY_WINDOW:] for number in row.numbers)
    remaining.sort(key=lambda number: (-frequencies.get(number, 0), number))
    ticket_four = tuple(sorted(remaining[:_PICK_COUNT]))
    ticket_five = tuple(sorted(remaining[_PICK_COUNT : 2 * _PICK_COUNT]))
    return ticket_four, ticket_five


def _validated_disjoint_portfolio(
    tickets: tuple[tuple[int, ...], ...],
    strategy_id: str,
) -> tuple[tuple[int, ...], ...]:
    """Fail closed unless all tickets are pairwise disjoint, 30 numbers total.

    PortfolioBetAdapter only validates each ticket's own six numbers; it
    never compares tickets against each other, so cross-ticket disjointness
    must be checked here explicitly.
    """

    if len(tickets) != _NATIVE_TICKET_COUNT:
        raise InvalidOutput(f"{strategy_id}: expected {_NATIVE_TICKET_COUNT} tickets")
    seen: set[int] = set()
    for position, ticket in enumerate(tickets, start=1):
        if not seen.isdisjoint(ticket):
            raise InvalidOutput(f"{strategy_id}: cross-ticket overlap at ticket {position}")
        seen.update(ticket)
    if len(seen) != _NATIVE_TICKET_COUNT * _PICK_COUNT:
        raise InvalidOutput(f"{strategy_id}: portfolio must use 30 distinct numbers")
    return tickets


class BigLottoFourierMixedHybridK5Adapter(PortfolioBetAdapter):
    """Fourier chunk-K3 prefix plus a freshly recomputed hot-frequency tail."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Fourier3+Hot2 混合研究 5注"
    strategy_version = "v0.1"
    min_history = _HISTORY_WINDOW
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_HISTORY_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")

        fourier_tickets = BigLottoFourierChunkK3Adapter().get_bets(history, lottery_type)
        if len(fourier_tickets) != _FOURIER_TICKET_COUNT:
            raise InvalidOutput(
                f"{self.strategy_id}: expected {_FOURIER_TICKET_COUNT} Fourier prefix tickets"
            )
        used = frozenset(number for ticket in fourier_tickets for number in ticket)
        if len(used) != _FOURIER_TICKET_COUNT * _PICK_COUNT:
            raise InvalidOutput(f"{self.strategy_id}: Fourier prefix tickets must be disjoint")

        ticket_four, ticket_five = _hot_tail_tickets(history, used)
        return _validated_disjoint_portfolio(
            (*fourier_tickets, ticket_four, ticket_five), self.strategy_id
        )


__all__ = ["BigLottoFourierMixedHybridK5Adapter"]
