"""Pure synthetic builders for historical-prefix analytics tests."""

from __future__ import annotations

from collections.abc import Iterable

from lottolab.domain.historical_results import (
    HistoricalDatasetDescriptor,
    HistoricalDrawSnapshot,
    HistoricalGovernanceStatus,
    HistoricalIdentityKind,
    HistoricalLotteryType,
    HistoricalPortfolio,
    HistoricalRunImport,
    HistoricalSourceDescriptor,
    HistoricalSourceKind,
    HistoricalStrategyDescriptor,
    HistoricalTicket,
)

DEFAULT_STRATEGY_ID = "strategy_a"
DEFAULT_TARGET_DRAW = 105
DEFAULT_CUTOFF_DRAW = 100


def build_descriptor(
    strategy_id: str = DEFAULT_STRATEGY_ID,
    *,
    strategy_version: str = "v1",
    replicate: int = 1,
    effective_strategy_id: str | None = None,
    identity_kind: HistoricalIdentityKind = HistoricalIdentityKind.REAL,
    governance_status: HistoricalGovernanceStatus = HistoricalGovernanceStatus.UNKNOWN,
    alias_of_strategy_id: str | None = None,
    equivalence_group: str | None = None,
    nested_prefix_supported: bool = True,
) -> HistoricalStrategyDescriptor:
    return HistoricalStrategyDescriptor(
        strategy_id=strategy_id,
        effective_strategy_id=effective_strategy_id or strategy_id,
        strategy_version=strategy_version,
        replicate=replicate,
        identity_kind=identity_kind,
        governance_status=governance_status,
        alias_of_strategy_id=alias_of_strategy_id,
        equivalence_group=equivalence_group,
        nested_prefix_supported=nested_prefix_supported,
        descriptor_sha256=f"{strategy_id}:{strategy_version}:{replicate}".encode()
        .hex()[:64]
        .ljust(64, "0"),
    )


def build_draw(
    draw_number: int,
    *,
    draw_date: str,
) -> HistoricalDrawSnapshot:
    return HistoricalDrawSnapshot(
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(7,),
        draw_sha256=f"{draw_number:064x}",
    )


def build_ticket(
    position: int,
    *,
    main_hit_count: int = 0,
    special_hit: bool = False,
) -> HistoricalTicket:
    start = ((position - 1) * 2) % 43 + 1
    main_numbers = tuple(range(start, start + 6))
    special_number = start + 6 if start + 6 <= 49 else 1
    return HistoricalTicket(
        portfolio_position=position,
        main_numbers=main_numbers,
        special_numbers=(special_number,),
        main_hit_count=main_hit_count,
        special_hit=special_hit,
        ticket_sha256=f"{position:02x}{main_hit_count:02x}{int(special_hit):02x}".ljust(64, "0"),
        legacy_row_id=None,
        legacy_storage_bet_index=None,
    )


def build_portfolio(
    strategy_id: str = DEFAULT_STRATEGY_ID,
    *,
    strategy_version: str = "v1",
    replicate: int = 1,
    target_draw_number: int = DEFAULT_TARGET_DRAW,
    cutoff_draw_number: int = DEFAULT_CUTOFF_DRAW,
    hit_counts: Iterable[int] | None = None,
    special_hits: Iterable[bool] | None = None,
    positions: Iterable[int] | None = None,
) -> HistoricalPortfolio:
    hits = tuple(hit_counts) if hit_counts is not None else (0,) * 20
    specials = tuple(special_hits) if special_hits is not None else (False,) * len(hits)
    ticket_positions = tuple(positions) if positions is not None else tuple(range(1, len(hits) + 1))
    if len(specials) != len(hits) or len(ticket_positions) != len(hits):
        raise ValueError("ticket fixture fields must have equal lengths")
    tickets = tuple(
        build_ticket(position, main_hit_count=hit, special_hit=special)
        for position, hit, special in zip(ticket_positions, hits, specials, strict=True)
    )
    return HistoricalPortfolio(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        replicate=replicate,
        target_draw_number=target_draw_number,
        cutoff_draw_number=cutoff_draw_number,
        constructor_identifier="prefix_analytics_test_builder",
        source_record_locator=None,
        tickets=tickets,
        portfolio_sha256=f"portfolio:{strategy_id}:{replicate}:{target_draw_number}".encode()
        .hex()[:64]
        .ljust(64, "0"),
        prefix10_sha256="1" * 64,
        prefix15_sha256="2" * 64,
    )


def build_run_import(
    *,
    descriptors: Iterable[HistoricalStrategyDescriptor] | None = None,
    draws: Iterable[HistoricalDrawSnapshot] | None = None,
    portfolios: Iterable[HistoricalPortfolio] | None = None,
) -> HistoricalRunImport:
    descriptors_tuple = tuple(descriptors or (build_descriptor(),))
    draws_tuple = tuple(
        draws
        or (
            build_draw(DEFAULT_CUTOFF_DRAW, draw_date="2026-01-01"),
            build_draw(DEFAULT_TARGET_DRAW, draw_date="2026-01-10"),
        )
    )
    portfolios_tuple = tuple(portfolios or (build_portfolio(),))
    return HistoricalRunImport(
        contract_version="1.0.0",
        generated_at="2026-01-11T00:00:00Z",
        manifest_sha256="a" * 64,
        import_identity_sha256="b" * 64,
        source=HistoricalSourceDescriptor(
            source_kind=HistoricalSourceKind.SYNTHETIC_TEST_ONLY,
            source_repository="github.com/kelvinhuang0327/MathStatisticalAnalysis",
            source_commit_oid="c" * 40,
            source_artifact_sha256="d" * 64,
            legacy_run_id=None,
        ),
        dataset=HistoricalDatasetDescriptor(
            dataset_identity="prefix-analytics-synthetic",
            dataset_sha256="e" * 64,
            lottery_type=HistoricalLotteryType.BIG_LOTTO,
        ),
        strategy_descriptors=descriptors_tuple,
        draw_snapshots=draws_tuple,
        portfolios=portfolios_tuple,
    )
