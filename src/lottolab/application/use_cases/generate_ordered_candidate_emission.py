"""Produce one legal bet and its producer-ordered emission from one execution."""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetResult,
    GenerateOneBetStatus,
    GeneratePortfolio,
    GeneratePortfolioResult,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_emission import (
    ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
    AuxiliaryOperandAvailability,
    AuxiliaryOperandKind,
    OrderedCandidateEmission,
)
from lottolab.strategies.adapters.base import CausalDrawRow


@dataclass(frozen=True, slots=True)
class GenerateOrderedCandidateEmissionInput:
    strategy_id: str
    lottery_type: LotteryType
    history: tuple[CausalDrawRow, ...]
    replicate: int
    target_draw: str
    history_cutoff: str


@dataclass(frozen=True, slots=True)
class GenerateOrderedCandidateEmissionResult:
    legal_bet: GenerateOneBetResult
    emission: OrderedCandidateEmission | None

    def __post_init__(self) -> None:
        if self.legal_bet.status is GenerateOneBetStatus.OK:
            if type(self.emission) is not OrderedCandidateEmission:
                raise ValueError("OK legal bets require an ordered emission")
        elif self.emission is not None:
            raise ValueError("non-OK legal bets must not carry an ordered emission")


def _missing_auxiliary_state(
    lottery_type: LotteryType,
) -> tuple[
    AuxiliaryOperandKind,
    AuxiliaryOperandAvailability,
    None,
]:
    if lottery_type is LotteryType.BIG_LOTTO:
        return (
            AuxiliaryOperandKind.BIG_LOTTO_SPECIAL,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        )
    if lottery_type is LotteryType.POWER_LOTTO:
        return (
            AuxiliaryOperandKind.POWER_LOTTO_ZONE2,
            AuxiliaryOperandAvailability.EXPLICITLY_MISSING,
            None,
        )
    return (
        AuxiliaryOperandKind.DAILY_539,
        AuxiliaryOperandAvailability.NOT_APPLICABLE,
        None,
    )


class GenerateOrderedCandidateEmission:
    """Expose raw producer order and the existing legal result without rerunning."""

    def __init__(self, generate_one_bet: GenerateOneBet) -> None:
        self._generate_one_bet = generate_one_bet

    def execute(
        self,
        request: GenerateOrderedCandidateEmissionInput,
    ) -> GenerateOrderedCandidateEmissionResult:
        execution = self._generate_one_bet.execute_with_emission(
            GenerateOneBetInput(
                strategy_id=request.strategy_id,
                lottery_type=request.lottery_type,
                history=request.history,
            )
        )
        if execution.legal_bet.status is not GenerateOneBetStatus.OK:
            return GenerateOrderedCandidateEmissionResult(
                legal_bet=execution.legal_bet,
                emission=None,
            )

        emitted_main_numbers = execution.emitted_main_numbers
        strategy_version = execution.strategy_version
        assert emitted_main_numbers is not None
        assert strategy_version is not None
        auxiliary_kind, auxiliary_availability, auxiliary_value = (
            _missing_auxiliary_state(request.lottery_type)
        )
        emission = OrderedCandidateEmission(
            schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
            lottery_type=request.lottery_type,
            strategy_id=request.strategy_id,
            strategy_version=strategy_version,
            replicate=request.replicate,
            target_draw=request.target_draw,
            history_cutoff=request.history_cutoff,
            emitted_main_numbers=emitted_main_numbers,
            auxiliary_operand_kind=auxiliary_kind,
            auxiliary_operand_availability=auxiliary_availability,
            auxiliary_operand_value=auxiliary_value,
        )
        return GenerateOrderedCandidateEmissionResult(
            legal_bet=execution.legal_bet,
            emission=emission,
        )


def build_production_generate_ordered_candidate_emission(
) -> GenerateOrderedCandidateEmission:
    return GenerateOrderedCandidateEmission(build_production_generate_one_bet())


@dataclass(frozen=True, slots=True)
class GenerateOrderedPortfolioEmissionInput:
    strategy_id: str
    lottery_type: LotteryType
    history: tuple[CausalDrawRow, ...]
    replicate: int
    target_draw: str
    history_cutoff: str


@dataclass(frozen=True, slots=True)
class GenerateOrderedPortfolioEmissionResult:
    legal_bets: GeneratePortfolioResult
    emissions: tuple[OrderedCandidateEmission, ...] | None

    def __post_init__(self) -> None:
        if self.legal_bets.status is GeneratePortfolioStatus.OK:
            if type(self.emissions) is not tuple or not self.emissions:
                raise ValueError("OK legal bets require ordered emissions")
            if any(
                type(emission) is not OrderedCandidateEmission
                for emission in self.emissions
            ):
                raise ValueError("every emission must be an OrderedCandidateEmission")
        elif self.emissions is not None:
            raise ValueError("non-OK legal bets must not carry ordered emissions")


class GenerateOrderedPortfolioEmission:
    """Expose raw producer order and the existing legal portfolio result.

    Mirrors :class:`GenerateOrderedCandidateEmission` for PORTFOLIO strategies:
    one call to :class:`GeneratePortfolio`, one :class:`OrderedCandidateEmission`
    per native ticket, in native order, never truncated to ticket #1.
    """

    def __init__(self, generate_portfolio: GeneratePortfolio) -> None:
        self._generate_portfolio = generate_portfolio

    def execute(
        self,
        request: GenerateOrderedPortfolioEmissionInput,
    ) -> GenerateOrderedPortfolioEmissionResult:
        execution = self._generate_portfolio.execute_with_emission(
            GenerateOneBetInput(
                strategy_id=request.strategy_id,
                lottery_type=request.lottery_type,
                history=request.history,
            )
        )
        if execution.legal_bets.status is not GeneratePortfolioStatus.OK:
            return GenerateOrderedPortfolioEmissionResult(
                legal_bets=execution.legal_bets,
                emissions=None,
            )

        emitted_all_numbers = execution.emitted_all_numbers
        strategy_version = execution.strategy_version
        assert emitted_all_numbers is not None
        assert strategy_version is not None
        auxiliary_kind, auxiliary_availability, auxiliary_value = (
            _missing_auxiliary_state(request.lottery_type)
        )
        emissions = tuple(
            OrderedCandidateEmission(
                schema_version=ORDERED_CANDIDATE_EMISSION_SCHEMA_VERSION,
                lottery_type=request.lottery_type,
                strategy_id=request.strategy_id,
                strategy_version=strategy_version,
                replicate=request.replicate,
                target_draw=request.target_draw,
                history_cutoff=request.history_cutoff,
                emitted_main_numbers=emitted_main_numbers,
                auxiliary_operand_kind=auxiliary_kind,
                auxiliary_operand_availability=auxiliary_availability,
                auxiliary_operand_value=auxiliary_value,
            )
            for emitted_main_numbers in emitted_all_numbers
        )
        return GenerateOrderedPortfolioEmissionResult(
            legal_bets=execution.legal_bets,
            emissions=emissions,
        )


def build_production_generate_ordered_portfolio_emission(
) -> GenerateOrderedPortfolioEmission:
    return GenerateOrderedPortfolioEmission(build_production_generate_portfolio())


__all__ = [
    "GenerateOrderedCandidateEmission",
    "GenerateOrderedCandidateEmissionInput",
    "GenerateOrderedCandidateEmissionResult",
    "GenerateOrderedPortfolioEmission",
    "GenerateOrderedPortfolioEmissionInput",
    "GenerateOrderedPortfolioEmissionResult",
    "build_production_generate_ordered_candidate_emission",
    "build_production_generate_ordered_portfolio_emission",
]
