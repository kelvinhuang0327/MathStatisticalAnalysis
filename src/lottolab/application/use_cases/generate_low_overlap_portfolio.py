"""Build a caller-sized low-overlap portfolio downstream of one bet.

This is an explicit application-layer construction path. It first executes an
existing ``SINGLE_TICKET`` strategy through :class:`GenerateOneBet`, retains
that legal native ticket, derives a deterministic candidate pool using the
existing P20 candidate-generation mechanics, and then delegates selection to
the reusable ``build_low_overlap_portfolio`` capability.

The path is intentionally separate from both ``GenerateOneBet`` and
``GeneratePortfolio``. It does not add a catalog identity, change predictor
semantics, or add ``k``/seed to ``BetAdapter``. The production path is scoped
to BIG_LOTTO because the reused P20 candidate-generation contract is the
native 6/49 universe. ``k=1`` remains the existing one-ticket path; this
construction path accepts only the explicit product ladder ``{2, 3, 5, 10,
20}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.application.strategy_preserving_20_ticket import (
    generate_seeded_candidate_pool,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.research import low_overlap_portfolio_constructor
from lottolab.strategies.adapters.base import CausalDrawRow

_ALLOWED_TICKET_COUNTS = frozenset((2, 3, 5, 10, 20))


class GenerateLowOverlapPortfolioStatus(StrEnum):
    OK = "OK"
    REJECTED = "REJECTED"
    INVALID_REQUEST = "INVALID_REQUEST"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"
    WRONG_RESPONSE_PATH = "WRONG_RESPONSE_PATH"


class GenerateLowOverlapPortfolioReason(StrEnum):
    INVALID_TICKET_COUNT = "INVALID_TICKET_COUNT"
    INVALID_CONSTRUCTION_SEED = "INVALID_CONSTRUCTION_SEED"
    REJECTED_BY_STRATEGY = "REJECTED_BY_STRATEGY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNKNOWN_STRATEGY = "UNKNOWN_STRATEGY"
    ADAPTER_NOT_INJECTED = "ADAPTER_NOT_INJECTED"
    UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"
    STRATEGY_IS_PORTFOLIO = "STRATEGY_IS_PORTFOLIO"


@dataclass(frozen=True, slots=True)
class GenerateLowOverlapPortfolioInput:
    """One explicit construction request with a path-owned ``k`` and seed."""

    strategy_id: str
    lottery_type: LotteryType
    history: tuple[CausalDrawRow, ...]
    k: int
    construction_seed: int


@dataclass(frozen=True, slots=True)
class GenerateLowOverlapPortfolioResult:
    """Closed result for a constructed native ticket set."""

    status: GenerateLowOverlapPortfolioStatus
    numbers: tuple[tuple[int, ...], ...] | None
    special_number: int | None
    reason_code: GenerateLowOverlapPortfolioReason | None

    def __post_init__(self) -> None:
        if self.status is GenerateLowOverlapPortfolioStatus.OK:
            if self.numbers is None or self.reason_code is not None:
                raise ValueError("OK results require numbers and no reason code")
        elif self.numbers is not None or self.reason_code is None:
            raise ValueError("non-OK results require a reason code and no numbers")


class GenerateLowOverlapPortfolio:
    """Compose one existing predictor with explicit low-overlap construction."""

    def __init__(self, generate_one_bet: GenerateOneBet) -> None:
        self._generate_one_bet = generate_one_bet

    def execute(
        self,
        request: GenerateLowOverlapPortfolioInput,
    ) -> GenerateLowOverlapPortfolioResult:
        if type(request.k) is not int or request.k not in _ALLOWED_TICKET_COUNTS:
            return self._failure(
                GenerateLowOverlapPortfolioStatus.INVALID_REQUEST,
                GenerateLowOverlapPortfolioReason.INVALID_TICKET_COUNT,
            )
        if type(request.construction_seed) is not int:
            return self._failure(
                GenerateLowOverlapPortfolioStatus.INVALID_REQUEST,
                GenerateLowOverlapPortfolioReason.INVALID_CONSTRUCTION_SEED,
            )
        if type(request.lottery_type) is not LotteryType or (
            request.lottery_type is not LotteryType.BIG_LOTTO
        ):
            return self._failure(
                GenerateLowOverlapPortfolioStatus.STRATEGY_UNAVAILABLE,
                GenerateLowOverlapPortfolioReason.UNSUPPORTED_LOTTERY_TYPE,
            )

        base_execution = self._generate_one_bet.execute_with_emission(
            GenerateOneBetInput(
                strategy_id=request.strategy_id,
                lottery_type=request.lottery_type,
                history=request.history,
            )
        )
        base_result = base_execution.legal_bet
        if base_result.status is not GenerateOneBetStatus.OK:
            return self._from_one_bet_failure(base_result.status, base_result.reason_code)

        base_numbers = base_result.numbers
        cutoff_row = (
            request.history[-1]
            if type(request.history) is tuple and request.history
            else None
        )
        if (
            type(base_numbers) is not tuple
            or base_result.special_number is not None
            or type(cutoff_row) is not CausalDrawRow
            or type(cutoff_row.draw) is not str
            or not cutoff_row.draw
        ):
            return self._failure(
                GenerateLowOverlapPortfolioStatus.INVALID_OUTPUT,
                GenerateLowOverlapPortfolioReason.INVALID_OUTPUT,
            )

        try:
            candidates = generate_seeded_candidate_pool(
                strategy_id=request.strategy_id,
                draw_id=cutoff_row.draw,
                user_seed=request.construction_seed,
                signal_tickets=(base_numbers,),
                required_count=request.k - 1,
            )
            candidate_pool = (base_numbers, *candidates)
            optional_scores = (1.0,) + (0.0,) * len(candidates)
            tickets = low_overlap_portfolio_constructor.build_low_overlap_portfolio(
                candidate_pool,
                request.k,
                BIG_LOTTO_RULE_CONTRACT,
                optional_scores=optional_scores,
            )
        except ValueError:
            return self._failure(
                GenerateLowOverlapPortfolioStatus.INVALID_OUTPUT,
                GenerateLowOverlapPortfolioReason.INVALID_OUTPUT,
            )
        except Exception:
            return self._failure(
                GenerateLowOverlapPortfolioStatus.REPLAY_ERROR,
                GenerateLowOverlapPortfolioReason.REPLAY_ERROR,
            )

        if (
            type(tickets) is not tuple
            or len(tickets) != request.k
            or len(set(tickets)) != request.k
            or base_numbers not in tickets
            or tickets[0] != base_numbers
        ):
            return self._failure(
                GenerateLowOverlapPortfolioStatus.INVALID_OUTPUT,
                GenerateLowOverlapPortfolioReason.INVALID_OUTPUT,
            )
        return GenerateLowOverlapPortfolioResult(
            status=GenerateLowOverlapPortfolioStatus.OK,
            numbers=tickets,
            special_number=None,
            reason_code=None,
        )

    @staticmethod
    def _from_one_bet_failure(
        status: GenerateOneBetStatus,
        reason: GenerateOneBetReason | None,
    ) -> GenerateLowOverlapPortfolioResult:
        if reason is None:
            return GenerateLowOverlapPortfolio._failure(
                GenerateLowOverlapPortfolioStatus.REPLAY_ERROR,
                GenerateLowOverlapPortfolioReason.REPLAY_ERROR,
            )
        return GenerateLowOverlapPortfolio._failure(
            GenerateLowOverlapPortfolioStatus(status.value),
            GenerateLowOverlapPortfolioReason(reason.value),
        )

    @staticmethod
    def _failure(
        status: GenerateLowOverlapPortfolioStatus,
        reason: GenerateLowOverlapPortfolioReason,
    ) -> GenerateLowOverlapPortfolioResult:
        return GenerateLowOverlapPortfolioResult(
            status=status,
            numbers=None,
            special_number=None,
            reason_code=reason,
        )


def build_production_generate_low_overlap_portfolio() -> GenerateLowOverlapPortfolio:
    """Build the explicit production path from the unchanged one-bet path."""

    return GenerateLowOverlapPortfolio(build_production_generate_one_bet())


__all__ = [
    "GenerateLowOverlapPortfolio",
    "GenerateLowOverlapPortfolioInput",
    "GenerateLowOverlapPortfolioReason",
    "GenerateLowOverlapPortfolioResult",
    "GenerateLowOverlapPortfolioStatus",
    "build_production_generate_low_overlap_portfolio",
]
