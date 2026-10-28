"""Research-only cutoff-aware ranking for the historical B649 K2/K3/K5 pool.

The module consumes the frozen strategy-pool metadata and already-produced
per-draw replay evidence. It never executes strategies, opens the production
database, or changes the frozen production Top-3.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = "B649_K235_CUTOFF_RANK_REFRESH_R1"
K_VALUES = (2, 3, 5)
WINDOW_SIZES: tuple[tuple[str, int | None], ...] = (
    ("FULL", None),
    ("50", 50),
    ("300", 300),
    ("750", 750),
    ("1500", 1500),
)
COMPLETE_STATUS = "COMPLETE"
INELIGIBLE_STATUS = "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS"
FATAL_STATUSES = frozenset({"EXECUTION_FAILURE", "NATIVE_TICKET_COUNT_VIOLATION"})


class RankRefreshInputError(ValueError):
    """Raised when source identities or per-draw outcomes cannot be trusted."""


@dataclass(frozen=True, slots=True)
class StrategyIdentity:
    strategy_id: str
    native_ticket_count: int
    display_name: str


@dataclass(frozen=True, slots=True)
class ReplayCell:
    strategy_id: str
    target_draw_number: str
    native_ticket_count: int
    replay_status: str
    official_any_prize: bool | None


def _draw_number(value: object, *, field_name: str) -> tuple[str, int]:
    if type(value) is int:
        if value <= 0:
            raise RankRefreshInputError(f"{field_name} must be a positive draw number")
        return str(value), value
    if type(value) is not str or not value.isdigit():
        raise RankRefreshInputError(f"{field_name} must contain decimal digits")
    number = int(value)
    if number <= 0:
        raise RankRefreshInputError(f"{field_name} must be a positive draw number")
    return value, number


def _strategy_pool(rank_history: Mapping[str, Any]) -> dict[str, StrategyIdentity]:
    raw_ids = rank_history.get("ids")
    if not isinstance(raw_ids, Mapping) or not raw_ids:
        raise RankRefreshInputError("rank_history.ids must be a non-empty mapping")

    pool: dict[str, StrategyIdentity] = {}
    for raw_strategy_id, raw_identity in cast(Mapping[object, Any], raw_ids).items():
        if type(raw_strategy_id) is not str or not raw_strategy_id.strip():
            raise RankRefreshInputError("strategy ids must be non-empty strings")
        if (
            not isinstance(raw_identity, Sequence)
            or isinstance(raw_identity, (str, bytes))
            or len(cast(Sequence[Any], raw_identity)) < 2
        ):
            raise RankRefreshInputError(
                f"rank_history identity for {raw_strategy_id} must contain K and name"
            )
        raw_identity = cast(Sequence[Any], raw_identity)
        ticket_count, display_name = raw_identity[0], raw_identity[1]
        if type(ticket_count) is not int or ticket_count not in K_VALUES:
            raise RankRefreshInputError(
                f"rank_history identity for {raw_strategy_id} has unsupported K"
            )
        if type(display_name) is not str:
            raise RankRefreshInputError(
                f"rank_history identity for {raw_strategy_id} has no display name"
            )
        pool[raw_strategy_id] = StrategyIdentity(
            strategy_id=raw_strategy_id,
            native_ticket_count=ticket_count,
            display_name=display_name,
        )
    return pool


def _rank_history_draws(rank_history: Mapping[str, Any]) -> list[str]:
    raw_draws = rank_history.get("cutoffs")
    if not isinstance(raw_draws, list):
        raise RankRefreshInputError("rank_history.cutoffs must be an ordered list")
    draws = [
        _draw_number(value, field_name="rank_history.cutoffs item")[0]
        for value in cast(list[object], raw_draws)
    ]
    if len(draws) != len(set(draws)):
        raise RankRefreshInputError("rank_history.cutoffs contains duplicate draws")
    if draws != sorted(draws, key=int):
        raise RankRefreshInputError("rank_history.cutoffs is not chronological")
    return draws


def _coerce_cell(value: ReplayCell | Mapping[str, Any]) -> ReplayCell:
    if isinstance(value, ReplayCell):
        return value
    if not isinstance(cast(object, value), Mapping):
        raise RankRefreshInputError("replay outcome must be a ReplayCell or mapping")
    strategy_id = value.get("strategy_id")
    if type(strategy_id) is not str or not strategy_id.strip():
        raise RankRefreshInputError("replay outcome strategy_id must be a non-empty string")
    draw, _ = _draw_number(value.get("target_draw_number"), field_name="target_draw_number")
    ticket_count = value.get("native_ticket_count")
    if type(ticket_count) is not int or ticket_count <= 0:
        raise RankRefreshInputError("replay outcome native_ticket_count must be positive")
    status = value.get("replay_status")
    if type(status) is not str or not status.strip():
        raise RankRefreshInputError("replay outcome replay_status must be non-empty")
    success = value.get("official_any_prize")
    if status == COMPLETE_STATUS and type(success) is not bool:
        raise RankRefreshInputError("COMPLETE replay outcomes require boolean official_any_prize")
    if status != COMPLETE_STATUS:
        success = None
    return ReplayCell(
        strategy_id=strategy_id,
        target_draw_number=draw,
        native_ticket_count=ticket_count,
        replay_status=status,
        official_any_prize=success,
    )


def load_rank_history(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the existing ranking source and return its byte-level identity."""
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RankRefreshInputError(f"invalid rank history JSON: {path}") from exc
    if not isinstance(document, dict):
        raise RankRefreshInputError("rank history document must be an object")
    identity = {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
    }
    return cast(dict[str, Any], document), identity


def load_replay_evidence(
    paths: Sequence[Path], strategy_pool: Mapping[str, StrategyIdentity]
) -> tuple[list[ReplayCell], list[dict[str, Any]], list[str]]:
    """Read existing JSONL outcomes, retaining only compact scored fields."""
    cells: list[ReplayCell] = []
    source_identities: list[dict[str, Any]] = []
    extra_strategy_ids: set[str] = set()

    for path in paths:
        digest = hashlib.sha256()
        record_count = 0
        pool_record_count = 0
        try:
            source = path.open("rb")
        except OSError as exc:
            raise RankRefreshInputError(f"cannot read replay evidence: {path}") from exc
        with source:
            for line_number, raw_line in enumerate(source, start=1):
                digest.update(raw_line)
                if not raw_line.strip():
                    continue
                record_count += 1
                try:
                    row = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RankRefreshInputError(f"invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(row, dict):
                    raise RankRefreshInputError(
                        f"JSONL row must be an object at {path}:{line_number}"
                    )
                row = cast(dict[str, Any], row)
                strategy_id = row.get("strategy_id")
                if type(strategy_id) is not str or strategy_id not in strategy_pool:
                    if type(strategy_id) is str and strategy_id.strip():
                        extra_strategy_ids.add(strategy_id)
                    continue
                pool_record_count += 1
                if row.get("target_outcome_excluded") is not True:
                    raise RankRefreshInputError(
                        f"target outcome was not excluded at {path}:{line_number}"
                    )
                target_draw, target_value = _draw_number(
                    row.get("target_draw_number"), field_name="target_draw_number"
                )
                causal_cutoff = row.get("causal_cutoff_draw_number")
                if causal_cutoff is not None:
                    _, causal_value = _draw_number(
                        causal_cutoff, field_name="causal_cutoff_draw_number"
                    )
                    if causal_value >= target_value:
                        raise RankRefreshInputError(
                            f"causal cutoff reaches target outcome at {path}:{line_number}"
                        )
                expected_identity = strategy_pool[strategy_id]
                native_ticket_count = row.get("native_ticket_count")
                if type(native_ticket_count) is not int or native_ticket_count <= 0:
                    raise RankRefreshInputError(
                        f"invalid native ticket count at {path}:{line_number}"
                    )
                status = row.get("replay_status")
                if type(status) is not str or not status.strip():
                    raise RankRefreshInputError(f"invalid replay status at {path}:{line_number}")
                actual_ticket_count = row.get("actual_native_ticket_count")
                if native_ticket_count != expected_identity.native_ticket_count or (
                    status == COMPLETE_STATUS
                    and actual_ticket_count != expected_identity.native_ticket_count
                ):
                    status = "NATIVE_TICKET_COUNT_VIOLATION"
                success = row.get("official_any_prize")
                if status == COMPLETE_STATUS and type(success) is not bool:
                    raise RankRefreshInputError(
                        f"COMPLETE row lacks official_any_prize at {path}:{line_number}"
                    )
                cells.append(
                    ReplayCell(
                        strategy_id=strategy_id,
                        target_draw_number=target_draw,
                        native_ticket_count=native_ticket_count,
                        replay_status=status,
                        official_any_prize=(success if status == COMPLETE_STATUS else None),
                    )
                )
        source_identities.append(
            {
                "path": str(path.resolve()),
                "sha256": digest.hexdigest(),
                "record_count": record_count,
                "strategy_pool_record_count": pool_record_count,
            }
        )
    return cells, source_identities, sorted(extra_strategy_ids)


def _rate(success_count: int, denominator: int) -> dict[str, Any] | None:
    if denominator == 0:
        return None
    return {
        "numerator": success_count,
        "denominator": denominator,
        "fraction": f"{success_count}/{denominator}",
        "decimal": success_count / denominator,
    }


def _window_metrics(
    *,
    strategy_id: str,
    draw_numbers: Sequence[str],
    window_name: str,
    requested_size: int | None,
    cells_by_draw: Mapping[str, ReplayCell],
) -> dict[str, Any]:
    successes = 0
    eligible = 0
    ineligible = 0
    execution_failures = 0
    unknown_statuses = 0
    missing_cells = 0
    ticket_count_violations = 0

    for draw_number in draw_numbers:
        cell = cells_by_draw.get(draw_number)
        if cell is None:
            missing_cells += 1
            continue
        if cell.native_ticket_count <= 0:
            ticket_count_violations += 1
            continue
        if cell.replay_status == COMPLETE_STATUS:
            if type(cell.official_any_prize) is not bool:
                unknown_statuses += 1
                continue
            eligible += 1
            successes += cell.official_any_prize
        elif cell.replay_status == INELIGIBLE_STATUS:
            ineligible += 1
        elif cell.replay_status in FATAL_STATUSES:
            execution_failures += 1
            if cell.replay_status == "NATIVE_TICKET_COUNT_VIOLATION":
                ticket_count_violations += 1
        else:
            unknown_statuses += 1

    if eligible == 0:
        status = "MISSING"
    elif missing_cells or execution_failures or unknown_statuses:
        status = "PARTIAL"
    elif requested_size is not None and len(draw_numbers) < requested_size:
        status = "INSUFFICIENT_HISTORY"
    else:
        status = "AVAILABLE"

    return {
        "window": window_name,
        "requested_draw_count": requested_size,
        "source_draw_count": len(draw_numbers),
        "first_target_draw": draw_numbers[0] if draw_numbers else None,
        "last_target_draw": draw_numbers[-1] if draw_numbers else None,
        "effective_denominator": eligible,
        "success_count": successes,
        "failure_count": eligible - successes,
        "success_rate": _rate(successes, eligible),
        "missing_cell_count": missing_cells,
        "ineligible_draw_count": ineligible,
        "execution_failure_count": execution_failures,
        "ticket_count_violation_count": ticket_count_violations,
        "unknown_status_count": unknown_statuses,
        "status": status,
        "strategy_id": strategy_id,
    }


def _baseline_validation(
    rank_history: Mapping[str, Any],
    cutoff_draw: str,
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    hist = rank_history.get("hist")
    snapshot = cast(Mapping[str, Any], hist).get(cutoff_draw) if isinstance(hist, Mapping) else None
    if not isinstance(snapshot, Mapping):
        return {"status": "NOT_AVAILABLE", "by_k": {f"K{k}": None for k in K_VALUES}}

    by_k: dict[str, Any] = {}
    for k_value in K_VALUES:
        historical_rows = cast(Mapping[str, Any], snapshot).get(str(k_value))
        if not isinstance(historical_rows, list):
            by_k[f"K{k_value}"] = {"status": "MISSING_BASELINE_ROWS"}
            continue
        expected: list[dict[str, Any]] = []
        for row in cast(list[Any], historical_rows):
            if not isinstance(row, list) or len(cast(list[Any], row)) < 5:
                raise RankRefreshInputError(
                    f"rank_history baseline row is malformed for K{k_value}"
                )
            row = cast(list[Any], row)
            expected.append(
                {
                    "rank": row[0],
                    "strategy_id": row[1],
                    "effective_denominator": row[3],
                    "success_count": row[4],
                }
            )
        actual = [
            {
                "rank": rank,
                "strategy_id": row["strategy_id"],
                "effective_denominator": row["windows"]["FULL"]["effective_denominator"],
                "success_count": row["windows"]["FULL"]["success_count"],
            }
            for rank, row in enumerate(rankings[f"K{k_value}"], start=1)
        ]
        matches = json.loads(json.dumps(expected)) == json.loads(json.dumps(actual))
        by_k[f"K{k_value}"] = {
            "status": "MATCH" if matches else "MISMATCH",
            "historical_ranked_count": len(expected),
            "recomputed_ranked_count": len(actual),
        }
    overall = (
        "MATCH"
        if all(
            isinstance(value, Mapping) and cast(Mapping[str, Any], value).get("status") == "MATCH"
            for value in by_k.values()
        )
        else "MISMATCH"
    )
    return {"status": overall, "by_k": by_k}


def build_cutoff_rank_refresh(
    rank_history: Mapping[str, Any],
    replay_cells: Iterable[ReplayCell | Mapping[str, Any]],
    cutoff_draw: str | int,
    *,
    rank_history_identity: Mapping[str, Any] | None = None,
    replay_source_identities: Sequence[Mapping[str, Any]] = (),
    extra_source_strategy_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build rankings at an inclusive outcome cutoff without future leakage."""
    requested_cutoff, cutoff_value = _draw_number(cutoff_draw, field_name="cutoff_draw")
    pool = _strategy_pool(rank_history)
    rank_history_draws = _rank_history_draws(rank_history)
    cells: dict[tuple[str, str], ReplayCell] = {}
    evidence_draws: set[str] = set()
    ignored_strategy_ids = set(extra_source_strategy_ids)

    for raw_cell in replay_cells:
        cell = _coerce_cell(raw_cell)
        if cell.strategy_id not in pool:
            ignored_strategy_ids.add(cell.strategy_id)
            continue
        if cell.native_ticket_count != pool[cell.strategy_id].native_ticket_count:
            cell = ReplayCell(
                strategy_id=cell.strategy_id,
                target_draw_number=cell.target_draw_number,
                native_ticket_count=cell.native_ticket_count,
                replay_status="NATIVE_TICKET_COUNT_VIOLATION",
                official_any_prize=None,
            )
        key = (cell.strategy_id, cell.target_draw_number)
        if key in cells:
            raise RankRefreshInputError(
                f"duplicate replay cell for {cell.strategy_id} at {cell.target_draw_number}"
            )
        cells[key] = cell
        evidence_draws.add(cell.target_draw_number)

    all_known_draws = sorted(set(rank_history_draws) | evidence_draws, key=int)
    latest_evidence_draw = max(evidence_draws, key=int) if evidence_draws else None
    cutoff_available = requested_cutoff in evidence_draws
    source_identities = {
        "rank_history": dict(rank_history_identity or {}),
        "per_draw_outcomes": [dict(item) for item in replay_source_identities],
    }
    pool_counts = {
        f"K{k_value}": sum(identity.native_ticket_count == k_value for identity in pool.values())
        for k_value in K_VALUES
    }

    if not cutoff_available:
        missing_strategies: list[dict[str, Any]] = [
            {
                "strategy_id": identity.strategy_id,
                "display_name": identity.display_name,
                "native_ticket_count": identity.native_ticket_count,
                "ranking_status": "MISSING",
                "missing_reason": "NO_OUTCOME_DATA_AT_REQUESTED_CUTOFF",
                "windows": {},
            }
            for identity in sorted(
                pool.values(), key=lambda item: (item.native_ticket_count, item.strategy_id)
            )
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": "RESEARCH_ONLY_CUTOFF_RANKING",
            "production_top3_mutated": False,
            "status": "MISSING",
            "cutoff": {
                "requested_draw_number": requested_cutoff,
                "actual_cutoff_applied": None,
                "inclusive_outcome_cutoff": True,
                "outcome_data_available": False,
                "latest_evidence_draw_number": latest_evidence_draw,
                "rank_history_latest_cutoff": (
                    rank_history_draws[-1] if rank_history_draws else None
                ),
            },
            "ranking_contract": {
                "lottery": "BIG_LOTTO",
                "success_definition": "any native ticket receives any official prize",
                "success_source_field": "official_any_prize",
                "cost_basis": "native_ticket_count_equals_K_within_each_ranking",
                "tie_break_order": [
                    "FULL success rate descending",
                    "FULL effective denominator descending",
                    "strategy_id ascending",
                ],
                "future_outcomes_used": False,
            },
            "windows": [
                {"name": name, "requested_draw_count": size} for name, size in WINDOW_SIZES
            ],
            "strategy_pool": {
                "strategy_count": len(pool),
                "count_by_k": pool_counts,
                "rankable_strategy_count": 0,
                "missing_strategy_count": len(pool),
                "strategy_pool_ids": sorted(pool),
                "covered_strategy_ids": [],
                "missing_strategy_ids": sorted(pool),
                "ignored_source_strategy_ids": sorted(ignored_strategy_ids),
            },
            "source_identity": source_identities,
            "source_coverage": {
                "rank_history_draw_count": len(rank_history_draws),
                "evidence_draw_count": len(evidence_draws),
                "latest_evidence_draw_number": latest_evidence_draw,
                "requested_cutoff_outcome_rows": sum(
                    1 for cell in cells.values() if cell.target_draw_number == requested_cutoff
                ),
            },
            "baseline_validation": {"status": "NOT_APPLICABLE", "by_k": {}},
            "rankings": {
                f"K{k_value}": {
                    "status": "MISSING",
                    "strategy_pool_count": pool_counts[f"K{k_value}"],
                    "ranked_strategy_count": 0,
                    "top3": [],
                    "missing_strategy_ids": sorted(
                        identity.strategy_id
                        for identity in pool.values()
                        if identity.native_ticket_count == k_value
                    ),
                }
                for k_value in K_VALUES
            },
            "strategies": missing_strategies,
        }

    target_draws = [draw for draw in all_known_draws if int(draw) <= cutoff_value]
    future_draws = [draw for draw in all_known_draws if int(draw) > cutoff_value]
    strategies: list[dict[str, Any]] = []
    candidate_rows: dict[str, list[dict[str, Any]]] = {f"K{k_value}": [] for k_value in K_VALUES}

    for identity in sorted(
        pool.values(), key=lambda item: (item.native_ticket_count, item.strategy_id)
    ):
        cells_by_draw = {
            draw: cell
            for (strategy_id, draw), cell in cells.items()
            if strategy_id == identity.strategy_id
        }
        windows: dict[str, dict[str, Any]] = {}
        for window_name, requested_size in WINDOW_SIZES:
            selected_draws = (
                target_draws if requested_size is None else target_draws[-requested_size:]
            )
            windows[window_name] = _window_metrics(
                strategy_id=identity.strategy_id,
                draw_numbers=selected_draws,
                window_name=window_name,
                requested_size=requested_size,
                cells_by_draw=cells_by_draw,
            )

        full = windows["FULL"]
        full_cell_count = sum(
            1
            for draw in target_draws
            if (cell := cells_by_draw.get(draw)) is not None
            and cell.replay_status in FATAL_STATUSES
        )
        unknown_cell_count = full["unknown_status_count"]
        missing_replay_cells = full["missing_cell_count"]
        if full_cell_count:
            missing_reason = "FATAL_REPLAY_STATUS_PRESENT"
        elif unknown_cell_count:
            missing_reason = "UNKNOWN_REPLAY_STATUS_PRESENT"
        elif full["ticket_count_violation_count"]:
            missing_reason = "NATIVE_TICKET_COUNT_VIOLATION_PRESENT"
        elif missing_replay_cells:
            missing_reason = "PER_DRAW_OUTCOME_CELL_MISSING"
        elif full["effective_denominator"] == 0:
            missing_reason = "NO_ELIGIBLE_OUTCOMES"
        else:
            missing_reason = None
        ranking_status = "MISSING" if missing_reason else "RANKABLE"

        strategy_row = {
            "strategy_id": identity.strategy_id,
            "display_name": identity.display_name,
            "native_ticket_count": identity.native_ticket_count,
            "ranking_status": ranking_status,
            "missing_reason": missing_reason,
            "windows": windows,
        }
        strategies.append(strategy_row)
        if ranking_status == "RANKABLE":
            candidate_rows[f"K{identity.native_ticket_count}"].append(strategy_row)

    for rows in candidate_rows.values():
        rows.sort(
            key=lambda row: (
                -Fraction(
                    row["windows"]["FULL"]["success_count"],
                    row["windows"]["FULL"]["effective_denominator"],
                ),
                -row["windows"]["FULL"]["effective_denominator"],
                row["strategy_id"],
            )
        )

    rankings: dict[str, Any] = {}
    for k_value in K_VALUES:
        key = f"K{k_value}"
        ranked = candidate_rows[key]
        missing_ids = sorted(
            identity.strategy_id
            for identity in pool.values()
            if identity.native_ticket_count == k_value
            and not any(row["strategy_id"] == identity.strategy_id for row in ranked)
        )
        top3: list[dict[str, Any]] = []
        for rank, row in enumerate(ranked[:3], start=1):
            top3.append(
                {
                    "rank": rank,
                    "strategy_id": row["strategy_id"],
                    "display_name": row["display_name"],
                    "native_ticket_count": k_value,
                    "windows": row["windows"],
                }
            )
        rankings[key] = {
            "status": "COMPLETE" if len(top3) == 3 else "PARTIAL",
            "strategy_pool_count": pool_counts[key],
            "ranked_strategy_count": len(ranked),
            "top3": top3,
            "missing_strategy_ids": missing_ids,
        }

    total_missing = sum(row["ranking_status"] == "MISSING" for row in strategies)
    overall_status = "PARTIAL" if total_missing else "COMPLETE"
    baseline_validation = _baseline_validation(rank_history, requested_cutoff, candidate_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "RESEARCH_ONLY_CUTOFF_RANKING",
        "production_top3_mutated": False,
        "status": overall_status,
        "cutoff": {
            "requested_draw_number": requested_cutoff,
            "actual_cutoff_applied": requested_cutoff,
            "inclusive_outcome_cutoff": True,
            "outcome_data_available": True,
            "latest_evidence_draw_number": latest_evidence_draw,
            "rank_history_latest_cutoff": (rank_history_draws[-1] if rank_history_draws else None),
            "included_target_draw_count": len(target_draws),
            "future_draw_count_excluded": len(future_draws),
            "future_outcomes_used": False,
        },
        "ranking_contract": {
            "lottery": "BIG_LOTTO",
            "success_definition": "any native ticket receives any official prize",
            "success_source_field": "official_any_prize",
            "cost_basis": "native_ticket_count_equals_K_within_each_ranking",
            "tie_break_order": [
                "FULL success rate descending",
                "FULL effective denominator descending",
                "strategy_id ascending",
            ],
            "future_outcomes_used": False,
            "window_selection": "last N target draws at or before cutoff; FULL uses all",
            "ineligible_rows": "excluded from effective denominator and reported",
            "missing_or_failed_rows": "never converted to failures or zero rates",
        },
        "windows": [{"name": name, "requested_draw_count": size} for name, size in WINDOW_SIZES],
        "strategy_pool": {
            "strategy_count": len(pool),
            "count_by_k": pool_counts,
            "rankable_strategy_count": len(strategies) - total_missing,
            "missing_strategy_count": total_missing,
            "strategy_pool_ids": sorted(pool),
            "covered_strategy_ids": sorted(
                row["strategy_id"] for row in strategies if row["ranking_status"] == "RANKABLE"
            ),
            "missing_strategy_ids": sorted(
                row["strategy_id"] for row in strategies if row["ranking_status"] == "MISSING"
            ),
            "ignored_source_strategy_ids": sorted(ignored_strategy_ids),
        },
        "source_identity": source_identities,
        "source_coverage": {
            "rank_history_draw_count": len(rank_history_draws),
            "evidence_draw_count": len(evidence_draws),
            "included_pool_outcome_cell_count": sum(
                int(cell.target_draw_number) <= cutoff_value for cell in cells.values()
            ),
            "requested_cutoff_outcome_rows": sum(
                cell.target_draw_number == requested_cutoff for cell in cells.values()
            ),
        },
        "baseline_validation": baseline_validation,
        "rankings": rankings,
        "strategies": strategies,
    }


def refresh_from_files(
    *,
    rank_history_path: Path,
    replay_paths: Sequence[Path],
    cutoff_draw: str | int,
) -> dict[str, Any]:
    """Read existing sources and return one serializable research artifact."""
    rank_history, rank_history_identity = load_rank_history(rank_history_path)
    pool = _strategy_pool(rank_history)
    cells, replay_identities, extra_ids = load_replay_evidence(replay_paths, pool)
    return build_cutoff_rank_refresh(
        rank_history,
        cells,
        cutoff_draw,
        rank_history_identity=rank_history_identity,
        replay_source_identities=replay_identities,
        extra_source_strategy_ids=extra_ids,
    )
