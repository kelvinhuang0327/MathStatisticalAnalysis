"""Research-only BIG_LOTTO Fourier chunk-K controlled cohort (K2, K3, K5).

The existing orthogonal 5-bet adapter uses Fourier for its first two tickets,
then different signals: lag-2 echo/cold frequency and hot frequency. This
family fixes one Fourier ranking and consecutive, disjoint six-number chunks
for every ticket. It does not take the first K tickets of that mixed-signal
strategy; only K2 has parity with its first two tickets. K5 need not match it.

All arms use the same latest 500 completed draws and require 500 for warm-up.
As in PortfolioBetAdapter, get_bets(history, lottery_type) accepts an immutable
oldest-first tuple of CausalDrawRow. For a target at sequence index t, callers
must supply only rows[:t]: the cutoff is exclusive of the target and every
future draw. We consume rows[max(0, t - 500):t], without reordering history.
There is no target/cutoff argument in this interface, so excluding target and
future rows is the caller's responsibility, not an inferred date/ID filter.

The donor's Fourier scores and NumPy-compatible unstable tie-break are reused
directly. Index zero is a score-vector sentinel, never a lottery number.
Within-ticket numbers are sorted; rank-chunk ticket order is preserved. K
changes only the number of chunks emitted. These new identities are not
registered in the production catalog and carry no performance evidence.
"""

from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_orthogonal_5bet as orthogonal
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput, PortfolioBetAdapter

_HISTORY_WINDOW = 500
_PICK_COUNT = 6
_MAX_NUMBER = 49
_FAMILY_ID = "research_biglotto__fourier_chunk"


def _fourier_chunk_tickets(
    history: tuple[CausalDrawRow, ...],
    ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """Partition one donor-compatible ranking; K never enters the scoring."""

    if ticket_count not in (2, 3, 5):
        raise InvalidOutput(f"{_FAMILY_ID}: supported ticket counts are 2, 3, 5")
    # Intentional private reuse keeps the frozen tie-break in one implementation.
    rank = orthogonal._fourier_rank(history)  # pyright: ignore[reportPrivateUsage]
    if (
        len(rank) != _MAX_NUMBER + 1
        or any(type(number) is not int for number in rank)
        or set(rank) != set(range(_MAX_NUMBER + 1))
    ):
        raise InvalidOutput(f"{_FAMILY_ID}: Fourier rank must permute indices 0..49")
    numbers = tuple(number for number in rank if number != 0)
    return tuple(
        tuple(sorted(numbers[start : start + _PICK_COUNT]))
        for start in range(0, ticket_count * _PICK_COUNT, _PICK_COUNT)
    )


class _BigLottoFourierChunkAdapter(PortfolioBetAdapter):
    """Shared warm-up, causal window, validation, and generation for all arms."""

    strategy_version = "v0.1"
    min_history = _HISTORY_WINDOW
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_HISTORY_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        return _fourier_chunk_tickets(history, self.native_ticket_count)


class BigLottoFourierChunkK2Adapter(_BigLottoFourierChunkAdapter):
    """First two Fourier chunks, matching the old orthogonal first two tickets."""

    strategy_id = f"{_FAMILY_ID}_k2"
    strategy_name = "大樂透 Fourier Chunk K2 研究 2注"
    native_ticket_count = 2


class BigLottoFourierChunkK3Adapter(_BigLottoFourierChunkAdapter):
    """First three chunks of the same Fourier ranking."""

    strategy_id = f"{_FAMILY_ID}_k3"
    strategy_name = "大樂透 Fourier Chunk K3 研究 3注"
    native_ticket_count = 3


class BigLottoFourierChunkK5Adapter(_BigLottoFourierChunkAdapter):
    """First five chunks of the same Fourier ranking."""

    strategy_id = f"{_FAMILY_ID}_k5"
    strategy_name = "大樂透 Fourier Chunk K5 研究 5注"
    native_ticket_count = 5


__all__ = [
    "BigLottoFourierChunkK2Adapter",
    "BigLottoFourierChunkK3Adapter",
    "BigLottoFourierChunkK5Adapter",
]
