"""Application-owned read models for the P638 Historical Results V2 vertical.

The models in this module are deliberately independent of SQLite and FastAPI.
The forwarding repository and the HTTP adapter translate their own storage and
wire representations into these immutable, lottery-scoped records.
"""

from __future__ import annotations

from dataclasses import dataclass

P638_LOTTERY_TYPE = "POWER_LOTTO"
P638_REPLAY_SORT = (
    "target_draw_date:asc",
    "target_draw_number:int_asc",
    "strategy_id:asc",
    "strategy_version:asc",
    "target_id:asc",
)
P638_STRATEGY_SORT = ("strategy_id:asc", "strategy_version:asc")
P638_ALLOWED_TARGET_STATUSES = (
    "COMPLETE",
    "EXCLUDED_INSUFFICIENT_HISTORY",
    "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE",
    "FAILED",
)
P638_QUERY_STATUS_ALIASES = (
    *P638_ALLOWED_TARGET_STATUSES,
    "COMPLETE_CAUSAL_REPLAY",
    "PRE_ELIGIBILITY",
    "SOURCE_NATIVE_TYPED_CLOSURE",
)


class P638HistoricalQueryError(RuntimeError):
    """Base class for sanitized P638 historical-query failures."""


class P638HistoricalResultsUnavailableError(P638HistoricalQueryError):
    """The configured Historical Results projection is unavailable."""


@dataclass(frozen=True, slots=True)
class P638RunSummary:
    run_id: str
    import_identity_sha256: str
    manifest_sha256: str
    contract_version: str
    source_run_id: str
    source_replay_sha256: str
    source_draw_db_sha256: str
    source_commit_oid: str
    source_content_sha256: str
    second_zone_ssot_version: str
    status: str
    started_at: str
    completed_at: str
    strategy_count: int
    draw_count: int
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    first_draw_number: str
    first_draw_date: str
    last_draw_number: str
    last_draw_date: str
    is_idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class P638RunPage:
    items: tuple[P638RunSummary, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class P638DrawRecord:
    draw_number: str
    draw_date: str
    winning_zone1_numbers: tuple[int, ...]
    winning_zone2_number: int


@dataclass(frozen=True, slots=True)
class P638DrawPage:
    run_id: str
    items: tuple[P638DrawRecord, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class P638StrategyRecord:
    strategy_snapshot_id: str
    run_id: str
    strategy_id: str
    display_label: str
    strategy_version: str
    executable: bool
    adapter_path: str | None
    native_ticket_count: int | None
    min_history: int | None
    zone1_contract: str
    zone2_contract: str
    lifecycle_status: str
    replay_status: str
    source_run_id: str | None
    source_replay_sha256: str | None
    source_paths: tuple[str, ...]
    provenance: str
    exclusion_reason: str | None
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    zone1_hit_distribution: tuple[tuple[int, int], ...]
    zone2_hit_distribution: tuple[tuple[int, int], ...]
    first_draw_number: str | None
    first_draw_date: str | None
    last_draw_number: str | None
    last_draw_date: str | None


@dataclass(frozen=True, slots=True)
class P638StrategyPage:
    run_id: str
    items: tuple[P638StrategyRecord, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class P638TicketRecord:
    ticket_id: str
    ticket_position: int
    predicted_zone1_numbers: tuple[int, ...]
    predicted_zone2_number: int
    actual_zone1_numbers: tuple[int, ...]
    actual_zone2_number: int
    zone1_hit_count: int
    zone2_hit: bool
    status: str
    source_run_id: str
    source_replay_sha256: str
    source_record_locator: str | None
    second_zone_ssot_version: str
    provenance: str
    is_winner: bool = False
    prize_tier: str | None = None
    prize_tier_order: int | None = None
    prize_amount: int | None = None


@dataclass(frozen=True, slots=True)
class P638ReplayRecord:
    target_id: str
    run_id: str
    strategy_snapshot_id: str
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    target_draw_date: str
    history_boundary_draw_number: str | None
    history_boundary_date: str | None
    history_length: int
    expected_ticket_count: int
    status: str
    exclusion_reason: str | None
    failure_reason: str | None
    actual_zone1_numbers: tuple[int, ...]
    actual_zone2_number: int
    source_target_locator: str | None
    source_run_id: str | None
    source_replay_sha256: str | None
    provenance: str
    tickets: tuple[P638TicketRecord, ...]
    reason_type: str | None = None
    reason: str | None = None
    target_success: bool | None = None


P638TargetDetail = P638ReplayRecord


@dataclass(frozen=True, slots=True)
class P638ReplayQuery:
    strategy_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class P638ReplayPage:
    run_id: str
    items: tuple[P638ReplayRecord, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class P638StrategyMetrics:
    run_id: str
    strategy_id: str | None
    target_count: int
    complete_target_count: int
    excluded_target_count: int
    failed_target_count: int
    ticket_count: int
    combined_zone1_4plus_zone2_hit_count: int
    zone1_hit_distribution: tuple[tuple[int, int], ...]
    zone2_hit_distribution: tuple[tuple[int, int], ...]
    first_draw_number: str | None
    first_draw_date: str | None
    last_draw_number: str | None
    last_draw_date: str | None


@dataclass(frozen=True, slots=True)
class P638RankingRecord:
    """One strategy's official-prize historical performance, all 10 always present.

    Ranking describes past replay only; it never predicts future winning.
    """

    run_id: str
    rank: int
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    eligible_target_count: int
    winning_target_count: int
    winning_target_rate: float
    total_complete_ticket_count: int
    winning_ticket_count: int
    ticket_winning_rate: float
    prize_tier_counts: tuple[tuple[str, int], ...]
    highest_prize_tier_achieved: str | None
    first_eligible_draw: str | None
    last_eligible_draw: str | None
    prize_rule_version: str
    prize_rule_provenance: str
    provenance: str


@dataclass(frozen=True, slots=True)
class P638RankingPage:
    run_id: str
    items: tuple[P638RankingRecord, ...]


@dataclass(frozen=True, slots=True)
class P638CurrentRankingPage:
    """Like :class:`P638RankingPage`, plus the active strategy-set fingerprint.

    The current-universe projection's strategy count is not fixed, so callers
    that need to detect "the active strategy set changed" compare this
    fingerprint (a SHA-256 of the sorted ``strategy_id@strategy_version``
    list) rather than a count.
    """

    run_id: str
    strategy_set_fingerprint: str
    items: tuple[P638RankingRecord, ...]


@dataclass(frozen=True, slots=True)
class P638ForwardingResult:
    run_id: str
    import_identity_sha256: str
    source_run_id: str
    source_replay_sha256: str
    source_draw_db_sha256: str
    strategy_count: int
    draw_count: int
    source_target_count: int
    source_complete_target_count: int
    source_excluded_target_count: int
    source_failed_target_count: int
    source_ticket_count: int
    forwarded_target_count: int
    forwarded_complete_target_count: int
    forwarded_excluded_target_count: int
    forwarded_failed_target_count: int
    forwarded_ticket_count: int
    excluded_strategy_count: int
    is_idempotent_replay: bool
