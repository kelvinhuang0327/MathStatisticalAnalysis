"""Builds the P638 current-universe official-prize historical ranking projection.

Distinct from ``p638_historical_forwarder.py``'s frozen P638 Historical
Results V2 contract (8 strategies, one pinned R4 source replay bundle that
must never be mutated), from ``p638_all10_ranking_forwarder.py``'s all-10
executable-strategy contract (Wave 1 only), and from
``p638_all23_ranking_forwarder.py``'s all-23 contract (Wave 1 plus Wave 2,
also never mutated by this module): this module runs a fresh causal replay
of every currently executable POWER_LOTTO strategy across Wave 1, Wave 2,
through Wave 5 (the exhaustive BIG_LOTTO cross-lottery portable set) against
the reconciled draw authority,
evaluates every complete ticket under the official POWER_LOTTO prize-tier
table, ranks every strategy by historical winning-target rate, and writes
the ``P638_HISTORICAL_RESULTS_CURRENT_PRIZE_RANKING_V1`` projection.

Unlike the all-10/all-23 contracts, the strategy count here is not fixed at
schema-design time: as later waves add strategies, ``CURRENT_STRATEGIES``
grows and this module keeps working unchanged. Callers that need to detect
"the active strategy set changed" read the stored ``strategy_set_fingerprint``
(a SHA-256 of the sorted ``strategy_id@strategy_version`` list) rather than
comparing a strategy count.

Both source databases (the draw authority and, transitively, the replay
runner's own read of it) are opened read-only; only the caller-provided
output database and the caller-provided replay database path are written.
Historical winning rank describes past replay only and does not guarantee
future winning.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.p638_historical import P638RankingRecord
from lottolab.domain.prize_evaluation import (
    POWER_LOTTO_PRIZE_RULE_CONTRACT,
    evaluate_power_lotto_ticket,
)
from lottolab.infrastructure.persistence.p638_current_ranking_schema import (
    CONTRACT_VERSION,
    initialize_schema,
    open_database,
)
from lottolab.research.powerlotto_wave1 import PowerLottoDrawRecord, normalize_draws, run_replay
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES, P638StrategySpec
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave3 import WAVE3_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave4 import WAVE4_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave5 import WAVE5_STRATEGIES

DRAW_DB_MIGRATION_ID = "P638_OLD_DB_DRAW_MIGRATION_R1"

CURRENT_STRATEGIES: tuple[P638StrategySpec, ...] = (
    WAVE1_STRATEGIES + WAVE2_STRATEGIES + WAVE3_STRATEGIES + WAVE4_STRATEGIES + WAVE5_STRATEGIES
)
CURRENT_SELECTED_STRATEGY_IDS: tuple[str, ...] = tuple(
    spec.strategy_id for spec in CURRENT_STRATEGIES
)


def strategy_set_fingerprint(strategies: Sequence[P638StrategySpec]) -> str:
    """SHA-256 of the sorted ``strategy_id@strategy_version`` list.

    Order-independent (sorted before hashing) so two runs with the same
    active strategy set always agree, regardless of tuple concatenation
    order across waves.
    """

    identities = sorted(f"{spec.strategy_id}@{spec.strategy_version}" for spec in strategies)
    canonical = json.dumps(identities, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


CURRENT_STRATEGY_SET_FINGERPRINT: str = strategy_set_fingerprint(CURRENT_STRATEGIES)

_TIER_IDS_BY_ORDER: tuple[str, ...] = tuple(
    tier.tier_id.value
    for tier in sorted(POWER_LOTTO_PRIZE_RULE_CONTRACT.tiers, key=lambda t: t.tier_order)
)


class P638CurrentRankingBuildError(RuntimeError):
    """The P638 current-universe replay/ranking build failed reconciliation."""


@dataclass(frozen=True, slots=True)
class P638CurrentRankingBuildResult:
    run_id: str
    contract_version: str
    strategy_set_fingerprint: str
    source_replay_db_sha256: str
    source_draw_db_sha256: str
    draw_count: int
    strategy_count: int
    excluded_strategy_count: int
    eligible_target_failure_count: int
    total_target_count: int
    total_complete_target_count: int
    total_excluded_target_count: int
    total_ticket_count: int
    replay_db_path: Path
    output_db_path: Path
    rankings: tuple[P638RankingRecord, ...]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_draws_from_draw_db(draw_db: Path) -> tuple[tuple[PowerLottoDrawRecord, ...], str]:
    """Read-only load of the reconciled POWER_LOTTO draw authority."""

    resolved = draw_db.resolve()
    draw_db_sha256 = _sha256_file(resolved)
    uri = f"{resolved.as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        migration = connection.execute(
            "SELECT migration_id FROM migration_run WHERE migration_id = ?",
            (DRAW_DB_MIGRATION_ID,),
        ).fetchone()
        if migration is None:
            raise P638CurrentRankingBuildError(
                f"draw database is missing the expected migration {DRAW_DB_MIGRATION_ID}"
            )
        rows = connection.execute(
            """
            SELECT draw_id, draw_number, draw_date, source_reference
            FROM lottery_draw
            WHERE lottery_type = 'POWER_LOTTO' AND status = 'COMPLETE'
            ORDER BY draw_date, draw_number
            """
        ).fetchall()
        if not rows:
            raise P638CurrentRankingBuildError("draw database has no POWER_LOTTO draws")
        draws: list[PowerLottoDrawRecord] = []
        for draw_id, draw_number, draw_date, source_reference in rows:
            zone1 = tuple(
                sorted(
                    int(number)
                    for (number,) in connection.execute(
                        "SELECT number FROM lottery_draw_number WHERE draw_id = ? AND zone = 1",
                        (draw_id,),
                    ).fetchall()
                )
            )
            if len(zone1) != 6:
                raise P638CurrentRankingBuildError(
                    f"draw {draw_number} does not have exactly six zone-1 numbers"
                )
            zone2_rows = connection.execute(
                "SELECT number FROM lottery_draw_number WHERE draw_id = ? AND zone = 2",
                (draw_id,),
            ).fetchall()
            if len(zone2_rows) != 1:
                raise P638CurrentRankingBuildError(
                    f"draw {draw_number} does not have exactly one zone-2 number"
                )
            draws.append(
                PowerLottoDrawRecord(
                    draw_number=str(draw_number),
                    draw_date=str(draw_date),
                    main_numbers=zone1,
                    second_number=int(zone2_rows[0][0]),
                    source_reference=str(source_reference),
                )
            )
    finally:
        connection.close()
    return normalize_draws(draws), draw_db_sha256


@dataclass(frozen=True, slots=True)
class _TargetRow:
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    target_draw_date: str
    cutoff_draw_number: str | None
    cutoff_index: int
    expected_ticket_count: int
    status: str
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class _TicketEvaluation:
    strategy_id: str
    target_draw_number: str
    ticket_position: int
    predicted_zone1: tuple[int, ...]
    predicted_zone2: int
    actual_zone1: tuple[int, ...]
    actual_zone2: int
    zone1_hits: int
    zone2_hit: bool
    is_winner: bool
    prize_tier: str | None
    prize_tier_order: int | None


def _read_replay_bundle(
    replay_db: Path, *, run_id: str, draws_by_number: dict[str, PowerLottoDrawRecord]
) -> tuple[tuple[_TargetRow, ...], tuple[_TicketEvaluation, ...]]:
    uri = f"{replay_db.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        target_rows = connection.execute(
            """
            SELECT strategy_id, strategy_version, target_draw_number, cutoff_draw_number,
                   cutoff_index, expected_ticket_count, status, failure_reason
            FROM strategy_targets
            WHERE run_id = ?
            ORDER BY strategy_id, cutoff_index
            """,
            (run_id,),
        ).fetchall()
        targets: list[_TargetRow] = []
        for (
            strategy_id,
            strategy_version,
            target_draw_number,
            cutoff_draw_number,
            cutoff_index,
            expected_ticket_count,
            status,
            failure_reason,
        ) in target_rows:
            actual_draw = draws_by_number.get(str(target_draw_number))
            if actual_draw is None:
                raise P638CurrentRankingBuildError(
                    f"target draw {target_draw_number} has no reconciled draw authority row"
                )
            targets.append(
                _TargetRow(
                    strategy_id=str(strategy_id),
                    strategy_version=str(strategy_version),
                    target_draw_number=str(target_draw_number),
                    target_draw_date=actual_draw.draw_date,
                    cutoff_draw_number=(
                        None if cutoff_draw_number is None else str(cutoff_draw_number)
                    ),
                    cutoff_index=int(cutoff_index),
                    expected_ticket_count=int(expected_ticket_count),
                    status=str(status),
                    failure_reason=None if failure_reason is None else str(failure_reason),
                )
            )

        ticket_rows = connection.execute(
            """
            SELECT strategy_id, target_draw_number, ticket_position,
                   predicted_main_numbers_json, predicted_second_number
            FROM tickets
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchall()
        tickets: list[_TicketEvaluation] = []
        for (
            strategy_id,
            target_draw_number,
            ticket_position,
            predicted_main_numbers_json,
            predicted_second_number,
        ) in ticket_rows:
            actual_draw = draws_by_number[str(target_draw_number)]
            predicted_zone1 = tuple(json.loads(predicted_main_numbers_json))
            predicted_zone2 = int(predicted_second_number)
            result = evaluate_power_lotto_ticket(
                predicted_main_numbers=predicted_zone1,
                predicted_special_number=predicted_zone2,
                winning_main_numbers=actual_draw.main_numbers,
                winning_special_number=actual_draw.second_number,
            )
            tickets.append(
                _TicketEvaluation(
                    strategy_id=str(strategy_id),
                    target_draw_number=str(target_draw_number),
                    ticket_position=int(ticket_position),
                    predicted_zone1=predicted_zone1,
                    predicted_zone2=predicted_zone2,
                    actual_zone1=actual_draw.main_numbers,
                    actual_zone2=actual_draw.second_number,
                    zone1_hits=result.zone1_hits,
                    zone2_hit=result.zone2_hit,
                    is_winner=result.is_winner,
                    prize_tier=result.prize_tier,
                    prize_tier_order=result.prize_tier_order,
                )
            )
    finally:
        connection.close()
    return tuple(targets), tuple(tickets)


def _compute_ranking(
    *,
    run_id: str,
    spec: P638StrategySpec,
    targets: Sequence[_TargetRow],
    tickets: Sequence[_TicketEvaluation],
) -> P638RankingRecord:
    complete_targets = [target for target in targets if target.status == "COMPLETE"]
    eligible_target_count = len(complete_targets)
    tickets_by_target: dict[str, list[_TicketEvaluation]] = {}
    for ticket in tickets:
        tickets_by_target.setdefault(ticket.target_draw_number, []).append(ticket)

    winning_target_count = 0
    winning_ticket_count = 0
    tier_counts: Counter[str] = Counter()
    for target in complete_targets:
        target_tickets = tickets_by_target.get(target.target_draw_number, ())
        target_is_winner = False
        for ticket in target_tickets:
            if ticket.is_winner:
                winning_ticket_count += 1
                target_is_winner = True
                assert ticket.prize_tier is not None
                tier_counts[ticket.prize_tier] += 1
        if target_is_winner:
            winning_target_count += 1

    total_complete_ticket_count = sum(
        len(tickets_by_target.get(target.target_draw_number, ())) for target in complete_targets
    )
    winning_target_rate = (
        winning_target_count / eligible_target_count if eligible_target_count else 0.0
    )
    ticket_winning_rate = (
        winning_ticket_count / total_complete_ticket_count if total_complete_ticket_count else 0.0
    )
    highest_prize_tier_achieved = next(
        (tier_id for tier_id in _TIER_IDS_BY_ORDER if tier_counts.get(tier_id, 0) > 0), None
    )
    ordered_draws = sorted(
        complete_targets, key=lambda t: (t.target_draw_date, int(t.target_draw_number))
    )
    first_eligible_draw = ordered_draws[0].target_draw_number if ordered_draws else None
    last_eligible_draw = ordered_draws[-1].target_draw_number if ordered_draws else None

    return P638RankingRecord(
        run_id=run_id,
        rank=0,  # assigned by the caller after sorting the whole current universe
        strategy_id=spec.strategy_id,
        strategy_version=spec.strategy_version,
        native_ticket_count=spec.native_ticket_count,
        eligible_target_count=eligible_target_count,
        winning_target_count=winning_target_count,
        winning_target_rate=winning_target_rate,
        total_complete_ticket_count=total_complete_ticket_count,
        winning_ticket_count=winning_ticket_count,
        ticket_winning_rate=ticket_winning_rate,
        prize_tier_counts=tuple(
            (tier_id, tier_counts.get(tier_id, 0)) for tier_id in _TIER_IDS_BY_ORDER
        ),
        highest_prize_tier_achieved=highest_prize_tier_achieved,
        first_eligible_draw=first_eligible_draw,
        last_eligible_draw=last_eligible_draw,
        prize_rule_version=POWER_LOTTO_PRIZE_RULE_CONTRACT.schema_version,
        prize_rule_provenance=(
            f"{POWER_LOTTO_PRIZE_RULE_CONTRACT.source_locator} "
            f"(sha256={POWER_LOTTO_PRIZE_RULE_CONTRACT.source_sha256})"
        ),
        provenance=spec.provenance,
    )


def _tier_count_vector(record: P638RankingRecord) -> tuple[int, ...]:
    return tuple(count for _tier_id, count in record.prize_tier_counts)


def _rank_key(record: P638RankingRecord) -> tuple[object, ...]:
    return (
        -record.winning_target_rate,
        tuple(-count for count in _tier_count_vector(record)),
        -record.ticket_winning_rate,
        -record.winning_target_count,
        -record.eligible_target_count,
        record.strategy_id,
    )


def _write_projection(
    *,
    output_db: Path,
    run_id: str,
    created_at: str,
    completed_at: str,
    draws: tuple[PowerLottoDrawRecord, ...],
    source_replay_db_sha256: str,
    source_draw_db_sha256: str,
    targets_by_strategy: dict[str, tuple[_TargetRow, ...]],
    tickets_by_strategy: dict[str, tuple[_TicketEvaluation, ...]],
    rankings: tuple[P638RankingRecord, ...],
) -> None:
    initialize_schema(output_db)
    with open_database(output_db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT 1 FROM p638_current_run WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return
            connection.execute(
                """
                INSERT INTO p638_current_run (
                    run_id, contract_version, lottery_type, strategy_set_fingerprint,
                    source_replay_db_sha256, source_draw_db_sha256, draw_count,
                    first_draw_number, last_draw_number, strategy_count,
                    excluded_strategy_count, eligible_target_failure_count,
                    prize_rule_version, prize_rule_provenance, created_at, completed_at
                ) VALUES (?, ?, 'POWER_LOTTO', ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    CONTRACT_VERSION,
                    CURRENT_STRATEGY_SET_FINGERPRINT,
                    source_replay_db_sha256,
                    source_draw_db_sha256,
                    len(draws),
                    draws[0].draw_number,
                    draws[-1].draw_number,
                    len(CURRENT_STRATEGIES),
                    POWER_LOTTO_PRIZE_RULE_CONTRACT.schema_version,
                    (
                        f"{POWER_LOTTO_PRIZE_RULE_CONTRACT.source_locator} "
                        f"(sha256={POWER_LOTTO_PRIZE_RULE_CONTRACT.source_sha256})"
                    ),
                    created_at,
                    completed_at,
                ),
            )
            for spec in CURRENT_STRATEGIES:
                connection.execute(
                    """
                    INSERT INTO p638_current_strategy (
                        run_id, strategy_id, strategy_version, native_ticket_count,
                        min_history, source_paths_json, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        spec.strategy_id,
                        spec.strategy_version,
                        spec.native_ticket_count,
                        spec.min_history,
                        json.dumps(spec.source_paths, ensure_ascii=False, separators=(",", ":")),
                        spec.provenance,
                    ),
                )

            target_ids: dict[tuple[str, str], str] = {}
            for spec in CURRENT_STRATEGIES:
                for target in targets_by_strategy.get(spec.strategy_id, ()):
                    identity = f"{run_id}|{target.strategy_id}|{target.target_draw_number}"
                    digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
                    target_id = f"p638-current-target-{digest}"
                    target_ids[(target.strategy_id, target.target_draw_number)] = target_id
                    connection.execute(
                        """
                        INSERT INTO p638_current_target (
                            id, run_id, strategy_id, strategy_version, target_draw_number,
                            target_draw_date, cutoff_draw_number, history_length,
                            expected_ticket_count, status, target_is_winner
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            target_id,
                            run_id,
                            target.strategy_id,
                            target.strategy_version,
                            target.target_draw_number,
                            target.target_draw_date,
                            target.cutoff_draw_number,
                            target.cutoff_index,
                            target.expected_ticket_count,
                            target.status,
                        ),
                    )

            for spec in CURRENT_STRATEGIES:
                target_winner: dict[str, bool] = {}
                for ticket in tickets_by_strategy.get(spec.strategy_id, ()):
                    target_id = target_ids.get((ticket.strategy_id, ticket.target_draw_number))
                    if target_id is None:
                        raise P638CurrentRankingBuildError(
                            "P638 current-universe ticket has no target row"
                        )
                    ticket_id = (
                        f"p638-current-ticket-"
                        f"{hashlib.sha256(f'{target_id}|{ticket.ticket_position}'.encode()).hexdigest()[:24]}"
                    )
                    connection.execute(
                        """
                        INSERT INTO p638_current_ticket (
                            id, target_id, run_id, strategy_id, target_draw_number,
                            ticket_position, predicted_zone1_numbers_json,
                            predicted_zone2_number, actual_zone1_numbers_json,
                            actual_zone2_number, zone1_hit_count, zone2_hit, is_winner,
                            prize_tier, prize_tier_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ticket_id,
                            target_id,
                            run_id,
                            ticket.strategy_id,
                            ticket.target_draw_number,
                            ticket.ticket_position,
                            json.dumps(ticket.predicted_zone1, separators=(",", ":")),
                            ticket.predicted_zone2,
                            json.dumps(ticket.actual_zone1, separators=(",", ":")),
                            ticket.actual_zone2,
                            ticket.zone1_hits,
                            int(ticket.zone2_hit),
                            int(ticket.is_winner),
                            ticket.prize_tier,
                            ticket.prize_tier_order,
                        ),
                    )
                    if ticket.is_winner:
                        target_winner[ticket.target_draw_number] = True
                for target_draw_number, target_id in (
                    (t.target_draw_number, target_ids[(spec.strategy_id, t.target_draw_number)])
                    for t in targets_by_strategy.get(spec.strategy_id, ())
                    if t.status == "COMPLETE"
                ):
                    connection.execute(
                        "UPDATE p638_current_target SET target_is_winner = ? WHERE id = ?",
                        (int(target_winner.get(target_draw_number, False)), target_id),
                    )

            for record in rankings:
                connection.execute(
                    """
                    INSERT INTO p638_current_ranking (
                        run_id, strategy_id, rank, strategy_version, native_ticket_count,
                        eligible_target_count, winning_target_count, winning_target_rate,
                        total_complete_ticket_count, winning_ticket_count, ticket_winning_rate,
                        prize_tier_counts_json, highest_prize_tier_achieved, first_eligible_draw,
                        last_eligible_draw, prize_rule_version, prize_rule_provenance, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.run_id,
                        record.strategy_id,
                        record.rank,
                        record.strategy_version,
                        record.native_ticket_count,
                        record.eligible_target_count,
                        record.winning_target_count,
                        record.winning_target_rate,
                        record.total_complete_ticket_count,
                        record.winning_ticket_count,
                        record.ticket_winning_rate,
                        json.dumps(dict(record.prize_tier_counts), ensure_ascii=False),
                        record.highest_prize_tier_achieved,
                        record.first_eligible_draw,
                        record.last_eligible_draw,
                        record.prize_rule_version,
                        record.prize_rule_provenance,
                        record.provenance,
                    ),
                )
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise P638CurrentRankingBuildError(
                    "P638 current-universe ranking projection left foreign-key violations"
                )
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()


def build_p638_current_ranking(
    *,
    draw_db: Path,
    runtime_root: Path,
    output_db: Path,
    replay_db_path: Path | None = None,
) -> P638CurrentRankingBuildResult:
    """Run the current-universe causal replay and build the ranking projection."""

    draws, draw_db_sha256 = _load_draws_from_draw_db(draw_db)
    replay_result = run_replay(
        draws=draws,
        strategy_objects=CURRENT_STRATEGIES,
        runtime_root=runtime_root,
        db_path=replay_db_path,
        selected_strategy_ids=CURRENT_SELECTED_STRATEGY_IDS,
    )
    if replay_result.failed_target_count != 0:
        raise P638CurrentRankingBuildError(
            "P638 current-universe replay produced failed targets: "
            f"{replay_result.failed_target_count}"
        )
    if replay_result.selected_count != len(CURRENT_STRATEGIES):
        raise P638CurrentRankingBuildError(
            "P638 current-universe replay did not select the full current strategy universe"
        )

    replay_db_sha256 = _sha256_file(replay_result.db_path)
    draws_by_number = {draw.draw_number: draw for draw in draws}
    targets, tickets = _read_replay_bundle(
        replay_result.db_path, run_id=replay_result.run_id, draws_by_number=draws_by_number
    )

    targets_by_strategy: dict[str, tuple[_TargetRow, ...]] = {}
    tickets_by_strategy: dict[str, tuple[_TicketEvaluation, ...]] = {}
    for spec in CURRENT_STRATEGIES:
        targets_by_strategy[spec.strategy_id] = tuple(
            target for target in targets if target.strategy_id == spec.strategy_id
        )
        tickets_by_strategy[spec.strategy_id] = tuple(
            ticket for ticket in tickets if ticket.strategy_id == spec.strategy_id
        )

    unranked = tuple(
        _compute_ranking(
            run_id=replay_result.run_id,
            spec=spec,
            targets=targets_by_strategy[spec.strategy_id],
            tickets=tickets_by_strategy[spec.strategy_id],
        )
        for spec in CURRENT_STRATEGIES
    )
    ordered = sorted(unranked, key=_rank_key)
    rankings = tuple(replace(record, rank=index) for index, record in enumerate(ordered, start=1))

    created_at = _utc_now()
    _write_projection(
        output_db=output_db,
        run_id=replay_result.run_id,
        created_at=created_at,
        completed_at=created_at,
        draws=draws,
        source_replay_db_sha256=replay_db_sha256,
        source_draw_db_sha256=draw_db_sha256,
        targets_by_strategy=targets_by_strategy,
        tickets_by_strategy=tickets_by_strategy,
        rankings=rankings,
    )

    return P638CurrentRankingBuildResult(
        run_id=replay_result.run_id,
        contract_version=CONTRACT_VERSION,
        strategy_set_fingerprint=CURRENT_STRATEGY_SET_FINGERPRINT,
        source_replay_db_sha256=replay_db_sha256,
        source_draw_db_sha256=draw_db_sha256,
        draw_count=len(draws),
        strategy_count=len(CURRENT_STRATEGIES),
        excluded_strategy_count=0,
        eligible_target_failure_count=0,
        total_target_count=len(targets),
        total_complete_target_count=replay_result.complete_target_count,
        total_excluded_target_count=replay_result.excluded_target_count,
        total_ticket_count=len(tickets),
        replay_db_path=replay_result.db_path,
        output_db_path=output_db,
        rankings=rankings,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "CURRENT_SELECTED_STRATEGY_IDS",
    "CURRENT_STRATEGIES",
    "CURRENT_STRATEGY_SET_FINGERPRINT",
    "DRAW_DB_MIGRATION_ID",
    "P638CurrentRankingBuildError",
    "P638CurrentRankingBuildResult",
    "build_p638_current_ranking",
    "strategy_set_fingerprint",
]
