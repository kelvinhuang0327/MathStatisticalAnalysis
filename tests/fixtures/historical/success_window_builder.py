"""Typed synthetic sources for Historical Prefix success-window tests."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date, timedelta

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessDrawIdentity,
    HistoricalPrefixSuccessSourceObservation,
    HistoricalPrefixSuccessSourceStrategy,
    HistoricalPrefixSuccessStrategyIdentity,
    HistoricalPrefixSuccessTicketOutcome,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixSuccessWindowSourceMetadata,
)
from lottolab.domain.historical_results import HistoricalLotteryType

OutcomeFactory = Callable[[int, int], tuple[int, bool]]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _default_outcome(_observation: int, _position: int) -> tuple[int, bool]:
    return (0, False)


def build_success_strategy_identity(
    strategy_id: str = "strategy-a",
    *,
    effective_strategy_id: str | None = None,
    strategy_version: str = "v1",
    replicate: int = 1,
    alias_of_strategy_id: str | None = None,
) -> HistoricalPrefixSuccessStrategyIdentity:
    return HistoricalPrefixSuccessStrategyIdentity(
        strategy_id=strategy_id,
        effective_strategy_id=effective_strategy_id or strategy_id,
        strategy_version=strategy_version,
        replicate=replicate,
        identity_kind="SYNTHETIC_TEST_ONLY",
        governance_status="CANDIDATE",
        alias_of_strategy_id=alias_of_strategy_id,
        equivalence_group=None,
        nested_prefix_supported=True,
        descriptor_sha256=_digest(
            f"{strategy_id}:{effective_strategy_id}:{strategy_version}:{replicate}:"
            f"{alias_of_strategy_id}"
        ),
    )


def build_success_observations(
    count: int,
    *,
    outcome_factory: OutcomeFactory | None = None,
    draw_number_offset: int = 1,
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    factory: OutcomeFactory = outcome_factory or _default_outcome
    base_date = date(2020, 1, 1)
    observations: list[HistoricalPrefixSuccessSourceObservation] = []
    for observation_index in range(count):
        draw_number = draw_number_offset + observation_index
        target_date = base_date + timedelta(days=observation_index + 1)
        cutoff_date = target_date - timedelta(days=1)
        tickets: list[HistoricalPrefixSuccessTicketOutcome] = []
        for position in range(1, 21):
            main_hit_count, special_hit = factory(observation_index, position)
            tickets.append(
                HistoricalPrefixSuccessTicketOutcome(
                    portfolio_position=position,
                    main_hit_count=main_hit_count,
                    special_hit=special_hit,
                    ticket_sha256=_digest(f"ticket:{draw_number}:{position}"),
                )
            )
        observations.append(
            HistoricalPrefixSuccessSourceObservation(
                target=HistoricalPrefixSuccessDrawIdentity(
                    draw_number=draw_number,
                    draw_date=target_date.isoformat(),
                    draw_sha256=_digest(f"target:{draw_number}"),
                ),
                cutoff=HistoricalPrefixSuccessDrawIdentity(
                    draw_number=max(1, draw_number - 1),
                    draw_date=cutoff_date.isoformat(),
                    draw_sha256=_digest(f"cutoff:{draw_number}"),
                ),
                constructor_identifier="synthetic-first-n-constructor",
                portfolio_sha256=_digest(f"portfolio:{draw_number}"),
                tickets=tuple(tickets),
            )
        )
    return tuple(observations)


def build_success_strategy(
    strategy_id: str = "strategy-a",
    *,
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...] = (),
    effective_strategy_id: str | None = None,
    strategy_version: str = "v1",
    replicate: int = 1,
    alias_of_strategy_id: str | None = None,
) -> HistoricalPrefixSuccessSourceStrategy:
    return HistoricalPrefixSuccessSourceStrategy(
        identity=build_success_strategy_identity(
            strategy_id,
            effective_strategy_id=effective_strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
            alias_of_strategy_id=alias_of_strategy_id,
        ),
        observations=observations,
    )


def build_success_source(
    strategies: tuple[HistoricalPrefixSuccessSourceStrategy, ...],
    *,
    import_identity_sha256: str = "a" * 64,
) -> HistoricalPrefixSuccessWindowSource:
    return HistoricalPrefixSuccessWindowSource(
        metadata=HistoricalPrefixSuccessWindowSourceMetadata(
            run_id="synthetic-run",
            contract_version="1.0.0",
            import_identity_sha256=import_identity_sha256,
            source_kind="SYNTHETIC_TEST_ONLY",
            source_repository="github.com/kelvinhuang0327/MathStatisticalAnalysis",
            source_commit_oid="c" * 40,
            source_artifact_sha256="d" * 64,
            dataset_identity="synthetic-dataset",
            dataset_sha256="e" * 64,
            lottery_type=HistoricalLotteryType.BIG_LOTTO,
        ),
        strategies=strategies,
    )


__all__ = [
    "build_success_observations",
    "build_success_source",
    "build_success_strategy",
    "build_success_strategy_identity",
]
