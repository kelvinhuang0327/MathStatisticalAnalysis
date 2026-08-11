"""Lottery adapters for the shared historical replay controller.

These wrappers reuse the existing pure strategy implementations.  They do
not register a strategy, open a database, read a file, call a network, or
change the existing adapter APIs.  The BIG_LOTTO wrapper also accepts a
streaming stored-output implementation for identities that are historical
raw-only and therefore must not execute an unavailable legacy producer.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.strategies.adapters.base import BetAdapterExecution, CausalDrawRow
from lottolab.strategies.adapters.daily539_portfolio_f4cold import Daily539F4ColdAdapter
from lottolab.strategies.adapters.powerlotto_wave1 import (
    WAVE1_STRATEGIES,
    P638HistoryRow,
    P638StrategySpec,
)
from lottolab.strategies.powerlotto_second_zone import MIN_HISTORY as P638_MIN_HISTORY


class ReplayStrategyImplementation(Protocol):
    strategy_id: str
    strategy_version: str
    min_history: int


@dataclass(frozen=True, slots=True)
class ReplayStrategyBinding:
    """Pair a pinned controller definition with one existing pure implementation."""

    strategy: ReplayStrategy
    implementation: object

    def __post_init__(self) -> None:
        implementation_id = getattr(self.implementation, "strategy_id", None)
        if implementation_id != self.strategy.strategy_id:
            raise ValueError("strategy binding identity does not match implementation")


class _PrizeEvaluatingAdapter:
    """Shared conversion from the canonical prize evaluator to replay records."""

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        outcome = evaluate_lottery_prize(
            lottery_type=target.lottery_type,
            predicted_main_numbers=ticket.main_numbers,
            predicted_special_number=ticket.special_number,
            winning_main_numbers=target.main_numbers,
            winning_special_number=target.special_number,
        )
        return ReplayEvaluation(
            zone1_hits=outcome.zone1_hits,
            zone2_hit=outcome.zone2_hit,
            is_winner=outcome.is_winner,
            prize_tier=outcome.prize_tier,
        )


class Daily539ReplayAdapter(_PrizeEvaluatingAdapter):
    """Target-native adapter for pure DAILY_539 strategy implementations."""

    lottery_type = LotteryType.DAILY_539

    def __init__(
        self,
        bindings: Iterable[ReplayStrategyBinding] | None = None,
        *,
        behavior: ReplayBehavior = ReplayBehavior.DETERMINISTIC,
    ) -> None:
        if bindings is None:
            implementation = Daily539F4ColdAdapter()
            bindings = (binding_from_implementation(implementation, behavior=behavior),)
        self._bindings = _freeze_bindings(bindings, LotteryType.DAILY_539)
        self._by_id: Mapping[str, ReplayStrategyBinding] = {
            binding.strategy.strategy_id: binding for binding in self._bindings
        }

    @property
    def strategies(self) -> tuple[ReplayStrategy, ...]:
        return tuple(binding.strategy for binding in self._bindings)

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        binding = self._binding(strategy)
        implementation = binding.implementation
        causal_rows = tuple(_daily539_row(draw) for draw in history)

        get_with_emission = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[BetAdapterExecution, ...]]
            | None,
            getattr(implementation, "get_bets_with_emission", None),
        )
        if callable(get_with_emission):
            executions = get_with_emission(causal_rows, LotteryType.DAILY_539)
            return tuple(
                ReplayTicket(
                    ticket_position=index,
                    main_numbers=execution.legal_main_numbers,
                    special_number=execution.special_number,
                )
                for index, execution in enumerate(executions, start=1)
            )

        get_bets = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[tuple[int, ...], ...]]
            | None,
            getattr(implementation, "get_bets", None),
        )
        if callable(get_bets):
            bets = get_bets(causal_rows, LotteryType.DAILY_539)
            return tuple(
                ReplayTicket(ticket_position=index, main_numbers=tuple(numbers))
                for index, numbers in enumerate(bets, start=1)
            )

        get_one_with_emission = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], BetAdapterExecution] | None,
            getattr(implementation, "get_one_bet_with_emission", None),
        )
        if callable(get_one_with_emission):
            execution = get_one_with_emission(causal_rows, LotteryType.DAILY_539)
            return (
                ReplayTicket(
                    ticket_position=1,
                    main_numbers=execution.legal_main_numbers,
                    special_number=execution.special_number,
                ),
            )

        get_one_bet = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[tuple[int, ...], int | None]]
            | None,
            getattr(implementation, "get_one_bet", None),
        )
        if callable(get_one_bet):
            numbers, special_number = get_one_bet(causal_rows, LotteryType.DAILY_539)
            return (ReplayTicket(1, tuple(numbers), special_number),)

        raise TypeError(f"{strategy.strategy_id}: implementation has no ticket method")

    def _binding(self, strategy: ReplayStrategy) -> ReplayStrategyBinding:
        try:
            binding = self._by_id[strategy.strategy_id]
        except KeyError as exc:
            raise ValueError(
                f"strategy {strategy.strategy_id!r} is not pinned in T539 adapter"
            ) from exc
        if binding.strategy.identity != strategy.identity:
            raise ValueError(f"strategy {strategy.strategy_id!r} identity is not pinned")
        return binding


class PowerLottoReplayAdapter(_PrizeEvaluatingAdapter):
    """Target-native adapter for the existing P638 Wave 1 strategy specs."""

    lottery_type = LotteryType.POWER_LOTTO

    def __init__(
        self,
        bindings: Iterable[ReplayStrategyBinding] | None = None,
        *,
        behavior: ReplayBehavior = ReplayBehavior.DETERMINISTIC,
    ) -> None:
        if bindings is None:
            bindings = tuple(
                binding_from_p638_spec(spec, behavior=behavior) for spec in WAVE1_STRATEGIES
            )
        self._bindings = _freeze_bindings(bindings, LotteryType.POWER_LOTTO)
        self._by_id: Mapping[str, ReplayStrategyBinding] = {
            binding.strategy.strategy_id: binding for binding in self._bindings
        }

    @property
    def strategies(self) -> tuple[ReplayStrategy, ...]:
        return tuple(binding.strategy for binding in self._bindings)

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        binding = self._binding(strategy)
        implementation = binding.implementation
        if not isinstance(implementation, P638StrategySpec):
            raise TypeError("POWER_LOTTO replay bindings require P638StrategySpec values")
        causal_rows = tuple(_p638_row(draw) for draw in history)
        tickets = implementation.get_bets(causal_rows, LotteryType.POWER_LOTTO)
        return tuple(
            ReplayTicket(
                ticket_position=index,
                main_numbers=first_zone,
                special_number=second_zone,
            )
            for index, (first_zone, second_zone) in enumerate(tickets, start=1)
        )

    def _binding(self, strategy: ReplayStrategy) -> ReplayStrategyBinding:
        try:
            binding = self._by_id[strategy.strategy_id]
        except KeyError as exc:
            raise ValueError(
                f"strategy {strategy.strategy_id!r} is not pinned in P638 adapter"
            ) from exc
        if binding.strategy.identity != strategy.identity:
            raise ValueError(f"strategy {strategy.strategy_id!r} identity is not pinned")
        return binding


class BigLottoReplayAdapter(_PrizeEvaluatingAdapter):
    """Target-native adapter for current and preserved BIG_LOTTO outputs."""

    lottery_type = LotteryType.BIG_LOTTO

    def __init__(self, bindings: Iterable[ReplayStrategyBinding]) -> None:
        self._bindings = _freeze_bindings(bindings, LotteryType.BIG_LOTTO)
        self._by_id: Mapping[str, ReplayStrategyBinding] = {
            binding.strategy.strategy_id: binding for binding in self._bindings
        }

    @property
    def strategies(self) -> tuple[ReplayStrategy, ...]:
        return tuple(binding.strategy for binding in self._bindings)

    def expected_native_ticket_count(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> int:
        """Return a source-native target count when a binding supplies one."""

        implementation = self._binding(strategy).implementation
        resolver = cast(
            Callable[[ReplayStrategy, tuple[ReplayDraw, ...], ReplayDraw], int] | None,
            getattr(implementation, "expected_native_ticket_count", None),
        )
        if callable(resolver):
            return resolver(strategy, history, target)
        return strategy.native_ticket_count

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        binding = self._binding(strategy)
        implementation = binding.implementation

        get_replay_tickets = cast(
            Callable[[tuple[ReplayDraw, ...], ReplayDraw], tuple[ReplayTicket, ...]] | None,
            getattr(implementation, "get_replay_tickets", None),
        )
        if callable(get_replay_tickets):
            tickets = get_replay_tickets(history, target)
            if type(tickets) is not tuple:
                raise TypeError("BIG_LOTTO stored-output implementations must return a tuple")
            return tickets

        causal_rows = tuple(_biglotto_row(draw) for draw in history)

        get_bets_with_emission = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[BetAdapterExecution, ...]]
            | None,
            getattr(implementation, "get_bets_with_emission", None),
        )
        if callable(get_bets_with_emission):
            executions = get_bets_with_emission(causal_rows, LotteryType.BIG_LOTTO)
            return tuple(
                ReplayTicket(
                    ticket_position=index,
                    main_numbers=execution.legal_main_numbers,
                    special_number=execution.special_number,
                )
                for index, execution in enumerate(executions, start=1)
            )

        get_bets = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[tuple[int, ...], ...]]
            | None,
            getattr(implementation, "get_bets", None),
        )
        if callable(get_bets):
            bets = get_bets(causal_rows, LotteryType.BIG_LOTTO)
            return tuple(
                ReplayTicket(ticket_position=index, main_numbers=tuple(numbers))
                for index, numbers in enumerate(bets, start=1)
            )

        get_one_with_emission = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], BetAdapterExecution] | None,
            getattr(implementation, "get_one_bet_with_emission", None),
        )
        if callable(get_one_with_emission):
            execution = get_one_with_emission(causal_rows, LotteryType.BIG_LOTTO)
            return (
                ReplayTicket(
                    ticket_position=1,
                    main_numbers=execution.legal_main_numbers,
                    special_number=execution.special_number,
                ),
            )

        get_one_bet = cast(
            Callable[[tuple[CausalDrawRow, ...], LotteryType], tuple[tuple[int, ...], None]]
            | None,
            getattr(implementation, "get_one_bet", None),
        )
        if callable(get_one_bet):
            numbers, special_number = get_one_bet(causal_rows, LotteryType.BIG_LOTTO)
            return (ReplayTicket(1, tuple(numbers), special_number),)

        raise TypeError(f"{strategy.strategy_id}: implementation has no ticket method")

    def _binding(self, strategy: ReplayStrategy) -> ReplayStrategyBinding:
        try:
            binding = self._by_id[strategy.strategy_id]
        except KeyError as exc:
            raise ValueError(
                f"strategy {strategy.strategy_id!r} is not pinned in BIG_LOTTO adapter"
            ) from exc
        if binding.strategy.identity != strategy.identity:
            raise ValueError(f"strategy {strategy.strategy_id!r} identity is not pinned")
        return binding


def binding_from_implementation(
    implementation: ReplayStrategyImplementation,
    *,
    behavior: ReplayBehavior = ReplayBehavior.DETERMINISTIC,
    fingerprint: str | None = None,
    seed_contract: str | None = None,
) -> ReplayStrategyBinding:
    """Build a controller binding from an existing DAILY_539-style adapter."""

    strategy_name = getattr(implementation, "strategy_name", implementation.strategy_id)
    native_ticket_count = getattr(implementation, "native_ticket_count", 1)
    if type(native_ticket_count) is not int:
        raise ValueError("native_ticket_count must be an exact integer when supplied")
    strategy = ReplayStrategy(
        strategy_id=implementation.strategy_id,
        strategy_name=strategy_name,
        strategy_version=implementation.strategy_version,
        behavior=behavior,
        native_ticket_count=native_ticket_count,
        min_history=implementation.min_history,
        fingerprint=fingerprint,
        seed_contract=seed_contract,
    )
    return ReplayStrategyBinding(strategy=strategy, implementation=implementation)


def t539_replay_bindings(
    *,
    strategy_ids: Sequence[str] | None = None,
    behavior_by_strategy: Mapping[str, ReplayBehavior] | None = None,
) -> tuple[ReplayStrategyBinding, ...]:
    """Return bindings for the existing sealed T539 adapter families.

    The list is assembled from the target-native DAILY_539 adapters already in
    the repository: fifteen direct identities, nine Batch15 identities, and
    the 38 portable BIG_LOTTO families.  No strategy is synthesized when an
    identity is absent.  Seeded families retain their explicit stochastic
    classification; callers may provide an audited behavior map for a pinned
    source configuration.
    """

    from lottolab.strategies.adapters.daily539_acb_markov_midfreq import (
        Daily539AcbMarkovMidfreqAdapter,
    )
    from lottolab.strategies.adapters.daily539_biglotto_batch15 import (
        DAILY539_BATCH15_ADAPTERS,
    )
    from lottolab.strategies.adapters.daily539_biglotto_portable import (
        DAILY539_BIGLOTTO_PORTABLE_SPECS,
        Daily539BigLottoPortableAdapter,
    )
    from lottolab.strategies.adapters.daily539_fourier4 import (
        Daily539P0bFourierColdFmidAdapter,
        Daily539P0cFourierColdX2Adapter,
    )
    from lottolab.strategies.adapters.daily539_portfolio_f4cold import (
        Daily539F4Cold3BetAdapter,
        Daily539F4Cold5BetAdapter,
        Daily539F4ColdAdapter,
    )
    from lottolab.strategies.adapters.daily539_portfolio_frequency import (
        Daily539MidfreqAcb2BetAdapter,
        Daily539MidfreqFourier2BetAdapter,
    )
    from lottolab.strategies.adapters.daily539_portfolio_phase2 import (
        Daily539AcbMarkovMidfreq3BetAdapter,
    )
    from lottolab.strategies.adapters.daily539_single_legacy import (
        Daily539Acb1BetAdapter,
        Daily539AcbSingleAdapter,
        Daily539Markov1BetAdapter,
        Daily539Orthogonal3BetAdapter,
    )
    from lottolab.strategies.adapters.daily539_wave1 import Daily539MarkovColdAdapter
    from lottolab.strategies.adapters.daily539_zone_gap import Daily539ZoneGap3BetAdapter

    implementations: list[object] = [
        Daily539Orthogonal3BetAdapter(),
        Daily539Acb1BetAdapter(),
        Daily539AcbMarkovMidfreqAdapter(),
        Daily539AcbMarkovMidfreq3BetAdapter(),
        Daily539AcbSingleAdapter(),
        Daily539F4ColdAdapter(),
        Daily539F4Cold3BetAdapter(),
        Daily539F4Cold5BetAdapter(),
        Daily539MarkovColdAdapter(),
        Daily539Markov1BetAdapter(),
        Daily539MidfreqAcb2BetAdapter(),
        Daily539MidfreqFourier2BetAdapter(),
        Daily539P0bFourierColdFmidAdapter(),
        Daily539P0cFourierColdX2Adapter(),
        Daily539ZoneGap3BetAdapter(),
        *(adapter() for adapter in DAILY539_BATCH15_ADAPTERS),
        *(Daily539BigLottoPortableAdapter(spec) for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS),
    ]
    requested = None if strategy_ids is None else frozenset(strategy_ids)
    behavior_overrides = behavior_by_strategy or {}
    seeded_ids = frozenset(
        {
            "t539_biglotto_random_core_satellite_3bet",
            "t539_biglotto_random_zone_split_3bet",
        }
    )
    bindings: list[ReplayStrategyBinding] = []
    for implementation in implementations:
        typed_implementation = cast(ReplayStrategyImplementation, implementation)
        strategy_id = typed_implementation.strategy_id
        if requested is not None and strategy_id not in requested:
            continue
        behavior = behavior_overrides.get(
            strategy_id,
            ReplayBehavior.SEEDED_STOCHASTIC
            if strategy_id in seeded_ids
            else ReplayBehavior.DETERMINISTIC,
        )
        bindings.append(
            binding_from_implementation(
                typed_implementation,
                behavior=behavior,
                seed_contract=(
                    "legacy_random_native/cpython_mt19937_v1"
                    if behavior is ReplayBehavior.SEEDED_STOCHASTIC
                    else None
                ),
            )
        )
    available_ids = {binding.strategy.strategy_id for binding in bindings}
    if requested is not None and frozenset(available_ids) != requested:
        missing = sorted(requested - available_ids)
        raise ValueError(f"T539 strategy identity has no existing adapter: {missing}")
    if not bindings:
        raise ValueError("T539 replay binding selection is empty")
    return tuple(bindings)


def binding_from_p638_spec(
    spec: P638StrategySpec,
    *,
    behavior: ReplayBehavior = ReplayBehavior.DETERMINISTIC,
    fingerprint: str | None = None,
    seed_contract: str | None = None,
) -> ReplayStrategyBinding:
    """Build a controller binding while preserving P638's second-zone SSOT."""

    resolved_fingerprint = fingerprint or sha256(spec.provenance.encode("utf-8")).hexdigest()
    strategy = ReplayStrategy(
        strategy_id=spec.strategy_id,
        strategy_name=f"P638 {spec.strategy_id}",
        strategy_version=spec.strategy_version,
        behavior=behavior,
        native_ticket_count=spec.native_ticket_count,
        min_history=max(spec.min_history, P638_MIN_HISTORY),
        fingerprint=resolved_fingerprint,
        seed_contract=seed_contract,
    )
    return ReplayStrategyBinding(strategy=strategy, implementation=spec)


def _freeze_bindings(
    bindings: Iterable[ReplayStrategyBinding], lottery_type: LotteryType
) -> tuple[ReplayStrategyBinding, ...]:
    frozen = tuple(bindings)
    if not frozen:
        raise ValueError(f"{lottery_type.value} replay adapter requires at least one strategy")
    ids = [binding.strategy.strategy_id for binding in frozen]
    if len(set(ids)) != len(ids):
        raise ValueError("replay adapter strategy ids must be unique")
    return frozen


def _daily539_row(draw: ReplayDraw) -> CausalDrawRow:
    if draw.lottery_type is not LotteryType.DAILY_539:
        raise ValueError("DAILY_539 adapter received a different draw type")
    if draw.special_number is not None:
        raise ValueError("DAILY_539 causal draws must not carry a second-zone value")
    return CausalDrawRow(
        draw=draw.draw_number,
        date=draw.draw_date.isoformat(),
        numbers=draw.main_numbers,
    )


def _biglotto_row(draw: ReplayDraw) -> CausalDrawRow:
    if draw.lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("BIG_LOTTO adapter received a different draw type")
    if draw.special_number is None:
        raise ValueError("BIG_LOTTO causal draws require a special number")
    return CausalDrawRow(
        draw=draw.draw_number,
        date=draw.draw_date.isoformat(),
        numbers=draw.main_numbers,
    )


def _p638_row(draw: ReplayDraw) -> P638HistoryRow:
    if draw.lottery_type is not LotteryType.POWER_LOTTO:
        raise ValueError("POWER_LOTTO adapter received a different draw type")
    if draw.special_number is None:
        raise ValueError("POWER_LOTTO causal draws require a second-zone value")
    return P638HistoryRow(
        draw=draw.draw_number,
        date=draw.draw_date.isoformat(),
        numbers=draw.main_numbers,
        second_number=draw.special_number,
    )


__all__ = [
    "BigLottoReplayAdapter",
    "Daily539ReplayAdapter",
    "PowerLottoReplayAdapter",
    "ReplayStrategyBinding",
    "binding_from_implementation",
    "binding_from_p638_spec",
    "t539_replay_bindings",
]
