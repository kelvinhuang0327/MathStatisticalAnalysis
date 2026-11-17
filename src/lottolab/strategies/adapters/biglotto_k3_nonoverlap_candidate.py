"""Research-only K3 portfolio candidates with deterministic ticket separation.

The donor adapters remain byte-identical to the fixed source commit. Each
candidate executes its donor first, then applies the same pure ticket transform.
"""

from __future__ import annotations

from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_wave4 import BigLottoThreeBetOptimizerAdapter
from lottolab.strategies.adapters.biglotto_wave14 import BigLottoTestEcpAdapter

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_TICKET_SIZE = 6
_TICKET_COUNT = 3


def _validated_source_tickets(
    tickets: object,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Require exactly three legal BIG_LOTTO tickets before transforming them."""

    if type(tickets) is not tuple or len(cast(tuple[object, ...], tickets)) != _TICKET_COUNT:
        raise ValueError("K3_NONOVERLAP_REQUIRES_EXACTLY_THREE_SOURCE_TICKETS")

    validated: list[tuple[int, ...]] = []
    for ticket in cast(tuple[object, ...], tickets):
        if type(ticket) is not tuple or len(cast(tuple[object, ...], ticket)) != _TICKET_SIZE:
            raise ValueError("K3_NONOVERLAP_SOURCE_TICKET_MUST_HAVE_SIX_NUMBERS")
        numbers = cast(tuple[object, ...], ticket)
        if any(type(number) is not int for number in numbers):
            raise ValueError("K3_NONOVERLAP_SOURCE_NUMBERS_MUST_BE_EXACT_INTEGERS")
        exact_numbers = cast(tuple[int, ...], numbers)
        if any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in exact_numbers):
            raise ValueError("K3_NONOVERLAP_SOURCE_NUMBER_OUT_OF_RANGE")
        if len(set(exact_numbers)) != _TICKET_SIZE:
            raise ValueError("K3_NONOVERLAP_SOURCE_TICKET_HAS_DUPLICATES")
        validated.append(exact_numbers)

    return validated[0], validated[1], validated[2]


def _retain_and_fill(source_ticket: tuple[int, ...], used_numbers: set[int]) -> tuple[int, ...]:
    """Keep unused donor numbers in order, then fill from the ascending pool."""

    ticket = [number for number in source_ticket if number not in used_numbers]
    used_numbers.update(ticket)
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if len(ticket) == _TICKET_SIZE:
            break
        if number not in used_numbers:
            ticket.append(number)
            used_numbers.add(number)

    if len(ticket) != _TICKET_SIZE:
        raise RuntimeError("K3_NONOVERLAP_NUMBER_POOL_EXHAUSTED")
    return tuple(ticket)


def make_k3_nonoverlap(
    source_tickets: object,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Keep T1; remove prior-ticket numbers from T2/T3 and fill ascending.

    The function is deterministic and reads only the supplied native output.
    Fallback numbers are behavior of this research candidate; they do not
    inherit the donor's candidate preferences or kill-number restrictions.
    It does not repair donor failures because callers invoke it only after a
    donor has returned three validated legal tickets.
    """

    ticket_1, ticket_2, ticket_3 = _validated_source_tickets(source_tickets)
    used_numbers = set(ticket_1)
    new_ticket_2 = _retain_and_fill(ticket_2, used_numbers)
    new_ticket_3 = _retain_and_fill(ticket_3, used_numbers)
    return ticket_1, new_ticket_2, new_ticket_3


class _K3NonoverlapCandidateAdapter(PortfolioBetAdapter):
    """Shared research adapter behavior; subclasses supply a native donor."""

    strategy_name = "K3 nonoverlap research candidate"
    strategy_version = "v1.0.0"
    min_history = 1
    supported_lottery_types = (cast(LotteryType, LotteryType.BIG_LOTTO),)
    native_ticket_count = _TICKET_COUNT
    donor_adapter_type: ClassVar[type[PortfolioBetAdapter]]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        source_tickets = self.donor_adapter_type().get_bets(history, lottery_type)
        return make_k3_nonoverlap(source_tickets)


class BigLottoK3NonoverlapOptimizerCandidateAdapter(_K3NonoverlapCandidateAdapter):
    """New research identity wrapping the frozen three-bet Optimizer donor."""

    strategy_id = "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116"
    strategy_name = "大樂透 K3 Optimizer 互斥研究候選"
    strategy_version = "v1.0.0"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    donor_adapter_type = BigLottoThreeBetOptimizerAdapter


class BigLottoK3NonoverlapEcpCandidateAdapter(_K3NonoverlapCandidateAdapter):
    """New research identity wrapping the frozen ECP donor."""

    strategy_id = "research_biglotto__k3_nonoverlap_ecp_candidate_20261116"
    strategy_name = "大樂透 K3 ECP 互斥研究候選"
    strategy_version = "v1.0.0"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    donor_adapter_type = BigLottoTestEcpAdapter
