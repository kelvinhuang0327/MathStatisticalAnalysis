"""Causal, regularized unequal-weight fusion for three BIG_LOTTO families.

The candidate reuses the executable K5 portfolios from the retained
cross-family parents.  It learns only a family ordering from an earlier train
block, selects one of three fixed non-uniform share profiles on a disjoint
later validation block, then applies those weights to the current target.
Every validation and target outcome is strictly after the training block.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from types import MappingProxyType, ModuleType
from typing import Final, cast

from lottolab.domain.lottery_rules import (
    BigLottoPrizeTier,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
)
from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _cooccurrence,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_network,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _omission,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryInput = Sequence[object]
type FamilyWeights = tuple[tuple[str, Fraction], ...]
type ParentProducer = Callable[[HistoryInput, int], object]

HYPOTHESIS_ID: Final[str] = "B649_REGULARIZED_UNEQUAL_WEIGHT_STACKING"
HYPOTHESIS_VERSION: Final[str] = "R1"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
PICK_COUNT: Final[int] = 6
PARENT_TICKET_BUDGET: Final[int] = 5
SUPPORTED_TICKET_BUDGETS: Final[tuple[int, int, int]] = (2, 3, 5)
MINIMUM_HISTORY: Final[int] = 751
TRAIN_TARGET_COUNT: Final[int] = 80
VALIDATION_TARGET_COUNT: Final[int] = 40
TRAINING_SIGNAL_COUNT: Final[int] = TRAIN_TARGET_COUNT + VALIDATION_TARGET_COUNT
VALIDATION_PRIOR_TARGETS: Final[int] = 120
COMPLEXITY_PENALTY: Final[Fraction] = Fraction(1, 50)
TICKET_COST_NTD: Final[int] = 50
SUCCESS_DEFINITION: Final[str] = "AT_LEAST_ONE_TICKET_WINS_ANY_OFFICIAL_BIG_LOTTO_PRIZE"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_TARGET_INDEX_ONLY"
SPLIT_RULE: Final[str] = "80_TRAIN_TARGETS_THEN_40_DISJOINT_VALIDATION_TARGETS"
WEIGHT_SELECTION_RULE: Final[str] = (
    "TRAIN_BLOCK_RANKS_FAMILIES;VALIDATION_BLOCK_SELECTS_ONE_OF_THREE_FIXED_PROFILES;"
    "PSEUDO_TARGET_SHRINKAGE_TO_TRAIN_BEST_SINGLE;L1_COMPLEXITY_PENALTY"
)

FAMILY_IDS: Final[tuple[str, str, str]] = (
    "CONDITIONAL_COOCCURRENCE",
    "GRAPH_NETWORK",
    "MULTISCALE_OMISSION_PRESSURE",
)
_FAMILY_PARENT_MODULES: Final[Mapping[str, tuple[ModuleType, str]]] = MappingProxyType(
    {
        "CONDITIONAL_COOCCURRENCE": (
            _cooccurrence,
            "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5",
        ),
        "GRAPH_NETWORK": (
            _graph_network,
            "produce_b649_graph_network_multiticket_low_overlap_v1_k5",
        ),
        "MULTISCALE_OMISSION_PRESSURE": (
            _omission,
            "produce_b649_multiscale_omission_pressure_multiticket_low_overlap_v1_k5",
        ),
    }
)
_WEIGHT_PROFILES: Final[tuple[tuple[str, tuple[Fraction, Fraction, Fraction]], ...]] = (
    (
        "SHARE_40_35_25",
        (Fraction(40, 100), Fraction(35, 100), Fraction(25, 100)),
    ),
    (
        "SHARE_45_35_20",
        (Fraction(45, 100), Fraction(35, 100), Fraction(20, 100)),
    ),
    (
        "SHARE_50_30_20",
        (Fraction(50, 100), Fraction(30, 100), Fraction(20, 100)),
    ),
)
_EQUAL_SHARES: Final[Fraction] = Fraction(1, 3)


class RequiredParentUnavailableError(ValueError):
    """Raised when a required family cannot supply a valid native K5 portfolio."""


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """One observed BIG_LOTTO outcome, indexed in chronological order."""

    target_index: int
    main_numbers: Ticket
    special_number: int
    draw_number: str | None = None


@dataclass(frozen=True, slots=True)
class FamilyReplaySignal:
    """Earlier target outcome and the three parent portfolios made before it."""

    target_index: int
    outcome: ReplayOutcome
    family_portfolios: Mapping[str, TicketPortfolio]


@dataclass(frozen=True, slots=True)
class WeightFit:
    """Auditable result of the bounded train/validation weighting procedure."""

    profile_id: str
    family_ranking: tuple[str, str, str]
    family_weights: FamilyWeights
    training_family_rates: tuple[tuple[str, Fraction], ...]
    selected_validation_successes: int
    validation_target_count: int
    regularized_validation_score: Fraction
    training_target_range: tuple[int, int]
    validation_target_range: tuple[int, int]


@dataclass(frozen=True, slots=True)
class FusionPlan:
    """Current target tickets plus enough provenance to inspect the fusion."""

    ticket_budget: int
    tickets: TicketPortfolio
    ticket_origins: tuple[str, ...]
    family_weights: FamilyWeights
    profile_id: str
    family_ranking: tuple[str, str, str]
    weight_fit: WeightFit
    current_family_portfolios: Mapping[str, TicketPortfolio]


@dataclass(frozen=True, slots=True)
class WalkForwardRecord:
    """One target-period comparison; it is descriptive, never a new holdout."""

    target_index: int
    draw_number: str | None
    ticket_budget: int
    tickets: TicketPortfolio
    ticket_origins: tuple[str, ...]
    family_weights: FamilyWeights
    profile_id: str
    fusion_success: bool
    causal_best_single_family_id: str
    causal_best_single_success: bool
    family_successes: tuple[tuple[str, bool], ...]
    weight_fit: WeightFit


def _validate_ticket(raw_ticket: object, location: str) -> Ticket:
    if type(raw_ticket) is not tuple:
        raise ValueError(f"{location} must be an immutable six-integer tuple")
    values = cast(tuple[object, ...], raw_ticket)
    if len(values) != PICK_COUNT or not all(type(value) is int for value in values):
        raise ValueError(f"{location} must contain exactly six integers")
    numbers = cast(Ticket, values)
    if any(number < NUMBER_DOMAIN[0] or number > NUMBER_DOMAIN[1] for number in numbers):
        raise ValueError(f"{location} contains a number outside 1..49")
    if any(left >= right for left, right in pairwise(numbers)):
        raise ValueError(f"{location} must be strictly ascending and unique")
    return numbers


def _validate_outcome(outcome: ReplayOutcome) -> ReplayOutcome:
    if type(outcome) is not ReplayOutcome:
        raise ValueError("outcome must be a ReplayOutcome")
    if type(outcome.target_index) is not int or outcome.target_index < 0:
        raise ValueError("outcome.target_index must be a non-negative integer")
    _validate_ticket(outcome.main_numbers, "outcome.main_numbers")
    if type(outcome.special_number) is not int or not 1 <= outcome.special_number <= 49:
        raise ValueError("outcome.special_number must be an integer in 1..49")
    if outcome.special_number in outcome.main_numbers:
        raise ValueError("the special number must not overlap the winning main numbers")
    if outcome.draw_number is not None and (
        type(outcome.draw_number) is not str or not outcome.draw_number
    ):
        raise ValueError("outcome.draw_number must be absent or non-empty text")
    return outcome


def _validate_family_portfolios(raw: object, location: str) -> Mapping[str, TicketPortfolio]:
    if not isinstance(raw, Mapping) or set(raw) != set(FAMILY_IDS):
        raise ValueError(f"{location} must contain exactly the three retained families")
    portfolios: dict[str, TicketPortfolio] = {}
    for family_id in FAMILY_IDS:
        value = raw[family_id]
        if isinstance(value, str | bytes | Mapping):
            raise ValueError(f"{location}[{family_id}] must be a ticket sequence")
        try:
            raw_tickets = tuple(cast(Sequence[object], value))
        except TypeError as error:
            raise ValueError(f"{location}[{family_id}] must be a ticket sequence") from error
        if len(raw_tickets) != PARENT_TICKET_BUDGET:
            raise ValueError(
                f"{location}[{family_id}] must contain exactly {PARENT_TICKET_BUDGET} tickets"
            )
        tickets = tuple(
            _validate_ticket(ticket, f"{location}[{family_id}][{index}]")
            for index, ticket in enumerate(raw_tickets)
        )
        if len(set(tickets)) != len(tickets):
            raise ValueError(f"{location}[{family_id}] contains duplicate tickets")
        portfolios[family_id] = tickets
    return MappingProxyType(portfolios)


def _produce_parent_portfolios(
    history: HistoryInput, target_index: int
) -> Mapping[str, TicketPortfolio]:
    prior_history = history[:target_index]
    portfolios: dict[str, object] = {}
    for family_id, (module, producer_name) in _FAMILY_PARENT_MODULES.items():
        producer = getattr(module, producer_name, None)
        if not callable(producer):
            raise RequiredParentUnavailableError(
                f"required family producer is unavailable: {family_id}/{producer_name}"
            )
        portfolios[family_id] = cast(ParentProducer, producer)(prior_history, target_index)
    return _validate_family_portfolios(portfolios, "current_family_portfolios")


def _signal_success(
    tickets: Sequence[Ticket], outcome: ReplayOutcome
) -> bool:
    winning = frozenset(outcome.main_numbers)
    for ticket in tickets:
        main_hits = sum(number in winning for number in ticket)
        special_hit = outcome.special_number in ticket
        result = resolve_big_lotto_prize_tier(main_hits, special_hit)
        if isinstance(result, BigLottoPrizeTier):
            return True
        if result is not NoPrizeResult.NO_PRIZE:
            raise ValueError("unknown official BIG_LOTTO prize result")
    return False


def _validate_signal_sequence(
    signals: Sequence[FamilyReplaySignal],
    *,
    name: str,
    target_index: int,
) -> tuple[FamilyReplaySignal, ...]:
    validated: list[FamilyReplaySignal] = []
    seen_indices: set[int] = set()
    previous_index = -1
    for position, signal in enumerate(signals):
        if type(signal) is not FamilyReplaySignal:
            raise ValueError(f"{name}[{position}] must be a FamilyReplaySignal")
        outcome = _validate_outcome(signal.outcome)
        if signal.target_index != outcome.target_index:
            raise ValueError(f"{name}[{position}] signal and outcome indices differ")
        if signal.target_index >= target_index:
            raise ValueError(
                f"{name}[{position}] target outcome must be strictly before target_index"
            )
        if signal.target_index <= previous_index or signal.target_index in seen_indices:
            raise ValueError(f"{name} target indices must be unique and chronological")
        portfolios = _validate_family_portfolios(
            signal.family_portfolios, f"{name}[{position}].family_portfolios"
        )
        validated.append(
            FamilyReplaySignal(signal.target_index, outcome, portfolios)
        )
        previous_index = signal.target_index
        seen_indices.add(signal.target_index)
    return tuple(validated)


def _profile_weights(
    family_ranking: tuple[str, str, str],
    shares: tuple[Fraction, Fraction, Fraction],
) -> FamilyWeights:
    if sum(shares, Fraction(0)) != 1 or any(share <= 0 for share in shares):
        raise ValueError("weight profile must be positive and sum to one")
    by_family = {family_id: shares[position] for position, family_id in enumerate(family_ranking)}
    return tuple((family_id, by_family[family_id]) for family_id in FAMILY_IDS)


def _weight_map(weights: FamilyWeights) -> dict[str, Fraction]:
    return dict(weights)


def _weighted_unique_portfolio(
    family_portfolios: Mapping[str, TicketPortfolio],
    family_weights: FamilyWeights,
    ticket_budget: int,
) -> tuple[TicketPortfolio, tuple[str, ...]]:
    if ticket_budget not in SUPPORTED_TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    portfolios = _validate_family_portfolios(family_portfolios, "family_portfolios")
    weights = _weight_map(family_weights)
    if set(weights) != set(FAMILY_IDS) or sum(weights.values(), Fraction(0)) != 1:
        raise ValueError("family weights must cover all families and sum to one")
    if any(weight <= 0 for weight in weights.values()):
        raise ValueError("family weights must be positive")

    # Weighted fair ordering gives each family a deterministic share of the K
    # slots. Duplicate tuples are skipped and that family's next ticket is tried.
    pending: list[tuple[Fraction, int, int]] = []
    for family_position, family_id in enumerate(FAMILY_IDS):
        heapq.heappush(
            pending,
            (Fraction(1, 2) / weights[family_id], family_position, 0),
        )

    tickets: list[Ticket] = []
    origins: list[str] = []
    seen: set[Ticket] = set()
    while pending and len(tickets) < ticket_budget:
        _, family_position, ticket_position = heapq.heappop(pending)
        family_id = FAMILY_IDS[family_position]
        family_tickets = portfolios[family_id]
        ticket = family_tickets[ticket_position]
        next_position = ticket_position + 1
        if next_position < len(family_tickets):
            heapq.heappush(
                pending,
                (
                    Fraction(2 * next_position + 1, 2) / weights[family_id],
                    family_position,
                    next_position,
                ),
            )
        if ticket in seen:
            continue
        seen.add(ticket)
        tickets.append(ticket)
        origins.append(family_id)

    if len(tickets) != ticket_budget:
        raise RequiredParentUnavailableError(
            "the three retained parents do not provide enough unique tickets "
            f"for K={ticket_budget}"
        )
    return tuple(tickets), tuple(origins)


def _fit_weights(
    training_signals: Sequence[FamilyReplaySignal],
    validation_signals: Sequence[FamilyReplaySignal],
    *,
    target_index: int,
    ticket_budget: int,
) -> WeightFit:
    if ticket_budget not in SUPPORTED_TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    if type(target_index) is not int or target_index < MINIMUM_HISTORY:
        raise ValueError(f"target_index must be at least {MINIMUM_HISTORY}")
    train = _validate_signal_sequence(
        training_signals, name="training_signals", target_index=target_index
    )
    validation = _validate_signal_sequence(
        validation_signals, name="validation_signals", target_index=target_index
    )
    if len(train) != TRAIN_TARGET_COUNT or len(validation) != VALIDATION_TARGET_COUNT:
        raise ValueError(
            "weight fitting requires exactly 80 train and 40 validation targets"
        )
    train_indices = {signal.target_index for signal in train}
    validation_indices = {signal.target_index for signal in validation}
    if train_indices.intersection(validation_indices):
        raise ValueError("training and validation target segments must not overlap")
    if train[-1].target_index >= validation[0].target_index:
        raise ValueError("training segment must end before the validation segment starts")

    raw_training_successes = {
        family_id: sum(
            _signal_success(
                signal.family_portfolios[family_id][:ticket_budget], signal.outcome
            )
            for signal in train
        )
        for family_id in FAMILY_IDS
    }
    pooled_rate = Fraction(
        sum(raw_training_successes.values()), len(train) * len(FAMILY_IDS)
    )
    # A shared 20-target prior shrinks each family toward the pooled training
    # rate; it does not inspect any validation or current target outcome.
    training_rates = {
        family_id: (raw_training_successes[family_id] + 20 * pooled_rate)
        / (len(train) + 20)
        for family_id in FAMILY_IDS
    }
    family_ranking = tuple(
        sorted(FAMILY_IDS, key=lambda family_id: (-training_rates[family_id], family_id))
    )
    best_single_training_rate = max(training_rates.values())

    scored_profiles: list[
        tuple[Fraction, Fraction, int, str, FamilyWeights, int]
    ] = []
    for profile_position, (profile_id, shares) in enumerate(_WEIGHT_PROFILES):
        weights = _profile_weights(family_ranking, shares)
        validation_successes = 0
        for signal in validation:
            tickets, _ = _weighted_unique_portfolio(
                signal.family_portfolios, weights, ticket_budget
            )
            validation_successes += _signal_success(tickets, signal.outcome)
        posterior_rate = (
            validation_successes
            + VALIDATION_PRIOR_TARGETS * best_single_training_rate
        ) / (len(validation) + VALIDATION_PRIOR_TARGETS)
        distance_from_equal = sum(
            (abs(weight - _EQUAL_SHARES) for _, weight in weights), Fraction(0)
        )
        regularized_score = posterior_rate - COMPLEXITY_PENALTY * distance_from_equal
        scored_profiles.append(
            (
                regularized_score,
                distance_from_equal,
                profile_position,
                profile_id,
                weights,
                validation_successes,
            )
        )

    # Maximize validation evidence after shrinkage and complexity penalty;
    # ties prefer the less concentrated fixed profile, then its stable ID.
    score, _, _, profile_id, weights, validation_successes = min(
        scored_profiles,
        key=lambda item: (-item[0], item[1], item[2]),
    )
    return WeightFit(
        profile_id=profile_id,
        family_ranking=cast(tuple[str, str, str], family_ranking),
        family_weights=weights,
        training_family_rates=tuple(
            (family_id, training_rates[family_id]) for family_id in FAMILY_IDS
        ),
        selected_validation_successes=validation_successes,
        validation_target_count=len(validation),
        regularized_validation_score=score,
        training_target_range=(train[0].target_index, train[-1].target_index),
        validation_target_range=(validation[0].target_index, validation[-1].target_index),
    )


def create_unequal_weight_fusion_plan(
    history: HistoryInput,
    target_index: int,
    ticket_budget: int,
    training_signals: Sequence[FamilyReplaySignal],
    validation_signals: Sequence[FamilyReplaySignal],
) -> FusionPlan:
    """Create a K2/K3/K5 plan using only signals strictly before target_index."""

    if ticket_budget not in SUPPORTED_TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    if not isinstance(history, Sequence):
        raise ValueError("history must be a chronological sequence")
    if type(target_index) is not int or target_index > len(history):
        raise ValueError("target_index must be an integer within history length")
    if target_index < MINIMUM_HISTORY:
        raise ValueError(f"target_index requires at least {MINIMUM_HISTORY} prior draws")

    fit = _fit_weights(
        training_signals,
        validation_signals,
        target_index=target_index,
        ticket_budget=ticket_budget,
    )
    current_portfolios = _produce_parent_portfolios(history, target_index)
    tickets, origins = _weighted_unique_portfolio(
        current_portfolios, fit.family_weights, ticket_budget
    )
    return FusionPlan(
        ticket_budget=ticket_budget,
        tickets=tickets,
        ticket_origins=origins,
        family_weights=fit.family_weights,
        profile_id=fit.profile_id,
        family_ranking=fit.family_ranking,
        weight_fit=fit,
        current_family_portfolios=current_portfolios,
    )


def produce_b649_unequal_weight_stacking_candidate_r1(
    history: HistoryInput,
    target_index: int,
    ticket_budget: int,
    training_signals: Sequence[FamilyReplaySignal],
    validation_signals: Sequence[FamilyReplaySignal],
) -> TicketPortfolio:
    """Return a constrained, train-fitted K2/K3/K5 portfolio for one target."""

    return create_unequal_weight_fusion_plan(
        history,
        target_index,
        ticket_budget,
        training_signals,
        validation_signals,
    ).tickets


def _create_plan_from_current_portfolios(
    current_portfolios: Mapping[str, TicketPortfolio],
    *,
    target_index: int,
    ticket_budget: int,
    training_signals: Sequence[FamilyReplaySignal],
    validation_signals: Sequence[FamilyReplaySignal],
) -> FusionPlan:
    fit = _fit_weights(
        training_signals,
        validation_signals,
        target_index=target_index,
        ticket_budget=ticket_budget,
    )
    tickets, origins = _weighted_unique_portfolio(
        current_portfolios, fit.family_weights, ticket_budget
    )
    return FusionPlan(
        ticket_budget=ticket_budget,
        tickets=tickets,
        ticket_origins=origins,
        family_weights=fit.family_weights,
        profile_id=fit.profile_id,
        family_ranking=fit.family_ranking,
        weight_fit=fit,
        current_family_portfolios=current_portfolios,
    )


def walk_forward_backtest(
    outcomes: Sequence[ReplayOutcome],
    ticket_budget: int,
    *,
    first_evaluation_index: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[WalkForwardRecord, ...]:
    """Run one K budget through the shared multi-budget replay engine."""

    if ticket_budget not in SUPPORTED_TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    return walk_forward_backtests(
        outcomes,
        (ticket_budget,),
        first_evaluation_index=first_evaluation_index,
        progress_callback=progress_callback,
    )[ticket_budget]


def walk_forward_backtests(
    outcomes: Sequence[ReplayOutcome],
    ticket_budgets: Sequence[int] = SUPPORTED_TICKET_BUDGETS,
    *,
    first_evaluation_index: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Mapping[int, tuple[WalkForwardRecord, ...]]:
    """Replay several K budgets while generating each parent signal only once.

    The first evaluation target defaults to the earliest target with 751 prior
    draws plus 80 train and 40 disjoint validation signals. Set
    ``first_evaluation_index`` later to evaluate a requested recent window while
    generating only its immediately preceding 120 parent signals.
    """

    budgets = tuple(ticket_budgets)
    if not budgets or len(set(budgets)) != len(budgets):
        raise ValueError("ticket_budgets must be a non-empty unique sequence")
    if any(budget not in SUPPORTED_TICKET_BUDGETS for budget in budgets):
        raise ValueError(f"ticket_budgets must be selected from {SUPPORTED_TICKET_BUDGETS}")
    if not isinstance(outcomes, Sequence):
        raise ValueError("outcomes must be a chronological sequence")
    validated_outcomes = tuple(_validate_outcome(outcome) for outcome in outcomes)
    if any(outcome.target_index != index for index, outcome in enumerate(validated_outcomes)):
        raise ValueError("outcome.target_index values must equal their chronological positions")
    history = tuple(outcome.main_numbers for outcome in validated_outcomes)

    minimum_evaluation_index = MINIMUM_HISTORY + TRAINING_SIGNAL_COUNT
    evaluation_start = (
        minimum_evaluation_index
        if first_evaluation_index is None
        else first_evaluation_index
    )
    if type(evaluation_start) is not int or evaluation_start < minimum_evaluation_index:
        raise ValueError(
            "first_evaluation_index must allow minimum parent history and all prior signals"
        )
    if evaluation_start >= len(validated_outcomes):
        return MappingProxyType({budget: () for budget in budgets})

    signal_start = evaluation_start - TRAINING_SIGNAL_COUNT
    signal_history: list[FamilyReplaySignal] = []
    records_by_budget: dict[int, list[WalkForwardRecord]] = {
        budget: [] for budget in budgets
    }
    total_parent_targets = len(validated_outcomes) - signal_start
    for target_index in range(signal_start, len(validated_outcomes)):
        current_portfolios = _produce_parent_portfolios(history, target_index)
        if target_index >= evaluation_start:
            training = tuple(signal_history[-TRAINING_SIGNAL_COUNT:-VALIDATION_TARGET_COUNT])
            validation = tuple(signal_history[-VALIDATION_TARGET_COUNT:])
            outcome = validated_outcomes[target_index]
            for ticket_budget in budgets:
                plan = _create_plan_from_current_portfolios(
                    current_portfolios,
                    target_index=target_index,
                    ticket_budget=ticket_budget,
                    training_signals=training,
                    validation_signals=validation,
                )
                family_rates = dict(plan.weight_fit.training_family_rates)
                selected_single = min(
                    FAMILY_IDS,
                    key=lambda family_id: (-family_rates[family_id], family_id),
                )
                records_by_budget[ticket_budget].append(
                    WalkForwardRecord(
                        target_index=target_index,
                        draw_number=outcome.draw_number,
                        ticket_budget=ticket_budget,
                        tickets=plan.tickets,
                        ticket_origins=plan.ticket_origins,
                        family_weights=plan.family_weights,
                        profile_id=plan.profile_id,
                        fusion_success=_signal_success(plan.tickets, outcome),
                        causal_best_single_family_id=selected_single,
                        causal_best_single_success=_signal_success(
                            current_portfolios[selected_single][:ticket_budget], outcome
                        ),
                        family_successes=tuple(
                            (
                                family_id,
                                _signal_success(
                                    current_portfolios[family_id][:ticket_budget], outcome
                                ),
                            )
                            for family_id in FAMILY_IDS
                        ),
                        weight_fit=plan.weight_fit,
                    )
                )
        signal_history.append(
            FamilyReplaySignal(
                target_index=target_index,
                outcome=validated_outcomes[target_index],
                family_portfolios=current_portfolios,
            )
        )
        if progress_callback is not None:
            progress_callback(target_index - signal_start + 1, total_parent_targets)
    return MappingProxyType(
        {budget: tuple(records) for budget, records in records_by_budget.items()}
    )


__all__ = [
    "CAUSAL_CUTOFF_RULE",
    "COMPLEXITY_PENALTY",
    "FAMILY_IDS",
    "HYPOTHESIS_ID",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "MINIMUM_HISTORY",
    "PARENT_TICKET_BUDGET",
    "SPLIT_RULE",
    "SUCCESS_DEFINITION",
    "SUPPORTED_TICKET_BUDGETS",
    "TICKET_COST_NTD",
    "TRAIN_TARGET_COUNT",
    "VALIDATION_TARGET_COUNT",
    "WEIGHT_SELECTION_RULE",
    "FamilyReplaySignal",
    "FamilyWeights",
    "FusionPlan",
    "ReplayOutcome",
    "WalkForwardRecord",
    "WeightFit",
    "create_unequal_weight_fusion_plan",
    "produce_b649_unequal_weight_stacking_candidate_r1",
    "walk_forward_backtest",
    "walk_forward_backtests",
]
