"""Causal 5/10/15/20-ticket BIG_LOTTO portfolio evaluation.

The evaluator never generates tickets.  It consumes one already-materialized,
ordered 20-ticket portfolio per successful strategy/draw execution and derives
all ticket-count variants strictly as prefixes of that same portfolio.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from fractions import Fraction
from typing import Any, cast

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
)
from lottolab.application.historical_success_random_baseline import (
    official_any_prize_probability,
    portfolio_success_probability,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.lottery_rules import (
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
)

INPUT_SCHEMA_VERSION = "BIG_LOTTO_MULTI_TICKET_BACKTEST_INPUT_V1"
REPORT_SCHEMA_VERSION = "BIG_LOTTO_MULTI_TICKET_BACKTEST_REPORT_V2"
BACKTEST_POLICY_VERSION = "BIG_LOTTO_CAUSAL_ORDERED_20_PREFIX_5_10_15_20_V1"
PREFIX_COUNTS = (5, 10, 15, 20)
WINDOWS = (
    ("FULL", None),
    ("RECENT_750", 750),
    ("RECENT_300", 300),
    ("RECENT_50", 50),
)
SUCCESS_CRITERIA = tuple(HistoricalPrefixSuccessCriterion)
RESEARCH_DISCLAIMER = (
    "Historical success rates and exact random-baseline differences are "
    "descriptive research only and do not guarantee future prizes."
)


class MultiTicketBacktestInputError(ValueError):
    """The source artifact cannot satisfy the causal portfolio contract."""


class PortfolioExecutionStatus(StrEnum):
    OK = "OK"
    CLOSED_INSUFFICIENT_HISTORY = "CLOSED_INSUFFICIENT_HISTORY"
    CLOSED_REJECTED = "CLOSED_REJECTED"
    CLOSED_INVALID_OUTPUT = "CLOSED_INVALID_OUTPUT"
    CLOSED_EXECUTION_ERROR = "CLOSED_EXECUTION_ERROR"


Ticket = tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class _Target:
    draw_number: str
    draw_date: date
    winning_main_numbers: Ticket
    winning_special_number: int


@dataclass(frozen=True, slots=True)
class _Execution:
    strategy_id: str
    strategy_version: str
    target_draw_number: str
    status: PortfolioExecutionStatus
    reason_code: str | None
    history_cutoff_draw_number: str | None
    history_cutoff_draw_date: date | None
    native_generation: dict[str, object] | None
    native_tickets: tuple[Ticket, ...]
    ordered_portfolio: tuple[Ticket, ...]
    portfolio_derivation: str | None
    candidate_k: int | None
    combination_count: int | None


def _required_text(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if type(value) is not str or not value:
        raise MultiTicketBacktestInputError(f"{context}: {key} must be non-empty")
    return value


def _optional_positive_int(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise MultiTicketBacktestInputError(
            f"{context}: {key} must be absent or a positive integer"
        )
    return value


def _parse_date(value: object, context: str) -> date:
    if type(value) is not str:
        raise MultiTicketBacktestInputError(f"{context}: date must be an ISO string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise MultiTicketBacktestInputError(f"{context}: invalid ISO date") from exc
    if parsed.isoformat() != value:
        raise MultiTicketBacktestInputError(f"{context}: date must be canonical ISO")
    return parsed


def _parse_ticket(value: object, context: str) -> Ticket:
    if not isinstance(value, list):
        raise MultiTicketBacktestInputError(f"{context}: ticket must be an array")
    numbers = cast(list[object], value)
    if len(numbers) != 6 or any(type(number) is not int for number in numbers):
        raise MultiTicketBacktestInputError(
            f"{context}: ticket must contain six exact integers"
        )
    typed = cast(list[int], numbers)
    ticket = tuple(typed)
    if (
        ticket != tuple(sorted(ticket))
        or len(set(ticket)) != 6
        or any(number < 1 or number > 49 for number in ticket)
    ):
        raise MultiTicketBacktestInputError(
            f"{context}: ticket must be sorted, unique, and within 1..49"
        )
    return cast(Ticket, ticket)


def _parse_ticket_list(
    value: object,
    context: str,
    *,
    exact_count: int | None = None,
    non_empty: bool = False,
) -> tuple[Ticket, ...]:
    if not isinstance(value, list):
        raise MultiTicketBacktestInputError(f"{context}: tickets must be an array")
    rows = cast(list[object], value)
    if exact_count is not None and len(rows) != exact_count:
        raise MultiTicketBacktestInputError(
            f"{context}: tickets must contain exactly {exact_count} positions"
        )
    if non_empty and not rows:
        raise MultiTicketBacktestInputError(f"{context}: tickets must not be empty")
    return tuple(
        _parse_ticket(candidate, f"{context}[{index}]")
        for index, candidate in enumerate(rows)
    )


def _parse_native_generation(
    value: object,
    *,
    context: str,
    target_draw_number: str,
    native_ticket_count: int,
    history_cutoff_draw_number: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MultiTicketBacktestInputError(
            f"{context}: native_generation must be absent or an object"
        )
    payload = cast(dict[str, object], value)
    for key in (
        "protocol",
        "legacy_method_id",
        "source_sha256",
        "target_draw_number",
        "seed_material",
        "seed_digest",
        "native_ticket_order",
    ):
        _required_text(cast(dict[str, Any], payload), key, context)
    for key in ("source_sha256", "seed_digest"):
        digest = cast(str, payload[key])
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise MultiTicketBacktestInputError(
                f"{context}: {key} must be a lowercase SHA-256"
            )
    if payload["target_draw_number"] != target_draw_number:
        raise MultiTicketBacktestInputError(
            f"{context}: native_generation target contradicts execution"
        )
    if payload.get("native_ticket_count") != native_ticket_count:
        raise MultiTicketBacktestInputError(
            f"{context}: native_generation ticket count contradicts execution"
        )
    replicate_id = payload.get("replicate_id")
    if type(replicate_id) is not int or replicate_id < 0:
        raise MultiTicketBacktestInputError(
            f"{context}: native_generation replicate_id is invalid"
        )
    if payload.get("candidate_k") is not None:
        raise MultiTicketBacktestInputError(
            f"{context}: candidate_k must retain separate execution semantics"
        )
    if payload.get("combination_count") is not None:
        raise MultiTicketBacktestInputError(
            f"{context}: combination_count must retain separate execution semantics"
        )
    generation_cutoff = payload.get("history_cutoff_draw_number")
    if generation_cutoff is not None:
        if (
            type(generation_cutoff) is not str
            or not generation_cutoff
            or generation_cutoff != history_cutoff_draw_number
        ):
            raise MultiTicketBacktestInputError(
                f"{context}: native_generation cutoff contradicts execution"
            )
        history_count = payload.get("history_draw_count")
        first_draw = payload.get("history_first_draw_number")
        source_order = payload.get("source_history_order")
        if (
            type(history_count) is not int
            or history_count < 1
            or type(first_draw) is not str
            or not first_draw
            or source_order not in ("OLDEST_FIRST", "RECENT_FIRST")
        ):
            raise MultiTicketBacktestInputError(
                f"{context}: native_generation history semantics are invalid"
            )
    return dict(payload)


def _parse_targets(document: dict[str, Any]) -> tuple[_Target, ...]:
    targets_value = document.get("targets")
    if not isinstance(targets_value, list) or not targets_value:
        raise MultiTicketBacktestInputError("targets must be a non-empty array")
    targets_raw = cast(list[object], targets_value)
    targets: list[_Target] = []
    seen_numbers: set[str] = set()
    seen_dates: set[date] = set()
    for index, candidate in enumerate(targets_raw):
        if not isinstance(candidate, dict):
            raise MultiTicketBacktestInputError(f"targets[{index}] must be an object")
        row = cast(dict[str, Any], candidate)
        context = f"targets[{index}]"
        draw_number = _required_text(row, "draw_number", context)
        draw_date = _parse_date(row.get("draw_date"), context)
        winning_main = _parse_ticket(row.get("winning_main_numbers"), context)
        special = row.get("winning_special_number")
        if type(special) is not int or not 1 <= special <= 49 or special in winning_main:
            raise MultiTicketBacktestInputError(
                f"{context}: winning_special_number is invalid"
            )
        if draw_number in seen_numbers or draw_date in seen_dates:
            raise MultiTicketBacktestInputError(
                "target draw numbers and dates must both be unique"
            )
        seen_numbers.add(draw_number)
        seen_dates.add(draw_date)
        targets.append(_Target(draw_number, draw_date, winning_main, special))
    ordered = tuple(sorted(targets, key=lambda target: (target.draw_date, target.draw_number)))
    if tuple(targets) != ordered:
        raise MultiTicketBacktestInputError(
            "targets must be in ascending draw-date/draw-number order"
        )
    return ordered


def _strictly_precedes_target(
    *,
    cutoff_number: str,
    cutoff_date: date,
    target: _Target,
) -> bool:
    if cutoff_date >= target.draw_date:
        return False
    if cutoff_number.isdecimal() and target.draw_number.isdecimal():
        return int(cutoff_number) < int(target.draw_number)
    return cutoff_number != target.draw_number


def _parse_executions(
    document: dict[str, Any],
    *,
    catalog: FullStrategyCatalog,
    targets: tuple[_Target, ...],
) -> tuple[_Execution, ...]:
    executions_value = document.get("executions")
    if not isinstance(executions_value, list):
        raise MultiTicketBacktestInputError("executions must be an array")
    executions_raw = cast(list[object], executions_value)
    target_by_number = {target.draw_number: target for target in targets}
    catalog_by_id = {record.strategy_id: record for record in catalog.records}
    executions: list[_Execution] = []
    seen: set[tuple[str, str]] = set()
    for index, candidate in enumerate(executions_raw):
        if not isinstance(candidate, dict):
            raise MultiTicketBacktestInputError(f"executions[{index}] must be an object")
        row = cast(dict[str, Any], candidate)
        context = f"executions[{index}]"
        strategy_id = _required_text(row, "strategy_id", context)
        strategy_version = _required_text(row, "strategy_version", context)
        target_draw_number = _required_text(row, "target_draw_number", context)
        record = catalog_by_id.get(strategy_id)
        if record is None:
            raise MultiTicketBacktestInputError(
                f"{context}: strategy is outside the 221-method universe"
            )
        if record.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS:
            raise MultiTicketBacktestInputError(
                f"{context}: duplicate aliases cannot execute independently"
            )
        if strategy_version != record.strategy_version:
            raise MultiTicketBacktestInputError(
                f"{context}: strategy_version does not match frozen catalog"
            )
        target = target_by_number.get(target_draw_number)
        if target is None:
            raise MultiTicketBacktestInputError(
                f"{context}: target is outside the dataset"
            )
        identity = (strategy_id, target_draw_number)
        if identity in seen:
            raise MultiTicketBacktestInputError(
                f"{context}: duplicate strategy/target execution"
            )
        seen.add(identity)
        try:
            status = PortfolioExecutionStatus(_required_text(row, "status", context))
        except ValueError as exc:
            raise MultiTicketBacktestInputError(
                f"{context}: status is outside the closed set"
            ) from exc

        reason_raw = row.get("reason_code")
        if reason_raw is not None and (type(reason_raw) is not str or not reason_raw):
            raise MultiTicketBacktestInputError(
                f"{context}: reason_code must be absent or non-empty"
            )
        reason_code = reason_raw

        if status is PortfolioExecutionStatus.OK:
            if reason_code is not None:
                raise MultiTicketBacktestInputError(
                    f"{context}: OK execution cannot carry reason_code"
                )
            cutoff_number = _required_text(
                row,
                "history_cutoff_draw_number",
                context,
            )
            cutoff_date = _parse_date(
                row.get("history_cutoff_draw_date"),
                f"{context}.history_cutoff_draw_date",
            )
            if not _strictly_precedes_target(
                cutoff_number=cutoff_number,
                cutoff_date=cutoff_date,
                target=target,
            ):
                raise MultiTicketBacktestInputError(
                    f"{context}: history cutoff is not strictly before target"
                )
            native_tickets = _parse_ticket_list(
                row.get("native_tickets"),
                f"{context}.native_tickets",
                non_empty=True,
            )
            declared_native_count = row.get("native_ticket_count")
            if declared_native_count != len(native_tickets):
                raise MultiTicketBacktestInputError(
                    f"{context}: native_ticket_count contradicts native_tickets"
                )
            native_generation = _parse_native_generation(
                row.get("native_generation"),
                context=f"{context}.native_generation",
                target_draw_number=target_draw_number,
                native_ticket_count=len(native_tickets),
                history_cutoff_draw_number=cutoff_number,
            )
            ordered_portfolio = _parse_ticket_list(
                row.get("ordered_portfolio"),
                f"{context}.ordered_portfolio",
                exact_count=20,
            )
            declared_portfolio_count = row.get("portfolio_ticket_count")
            if declared_portfolio_count != 20:
                raise MultiTicketBacktestInputError(
                    f"{context}: portfolio_ticket_count must be exactly 20"
                )
            portfolio_derivation = _required_text(
                row,
                "portfolio_derivation",
                context,
            )
            candidate_k = _optional_positive_int(row, "candidate_k", context)
            combination_count = _optional_positive_int(
                row,
                "combination_count",
                context,
            )
        else:
            if reason_code is None:
                raise MultiTicketBacktestInputError(
                    f"{context}: closed execution requires reason_code"
                )
            forbidden = (
                "native_tickets",
                "native_ticket_count",
                "native_generation",
                "ordered_portfolio",
                "portfolio_ticket_count",
                "portfolio_derivation",
                "candidate_k",
                "combination_count",
            )
            if any(key in row for key in forbidden):
                raise MultiTicketBacktestInputError(
                    f"{context}: closed execution cannot carry ticket semantics"
                )
            cutoff_number_raw = row.get("history_cutoff_draw_number")
            cutoff_date_raw = row.get("history_cutoff_draw_date")
            if cutoff_number_raw is None and cutoff_date_raw is None:
                cutoff_number = None
                cutoff_date = None
            elif type(cutoff_number_raw) is str and cutoff_number_raw:
                cutoff_number = cutoff_number_raw
                cutoff_date = _parse_date(
                    cutoff_date_raw,
                    f"{context}.history_cutoff_draw_date",
                )
                if not _strictly_precedes_target(
                    cutoff_number=cutoff_number,
                    cutoff_date=cutoff_date,
                    target=target,
                ):
                    raise MultiTicketBacktestInputError(
                        f"{context}: closed-result cutoff is not causal"
                    )
            else:
                raise MultiTicketBacktestInputError(
                    f"{context}: closed-result cutoff fields must be both present or absent"
                )
            native_tickets = ()
            native_generation = None
            ordered_portfolio = ()
            portfolio_derivation = None
            candidate_k = None
            combination_count = None

        executions.append(
            _Execution(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                target_draw_number=target_draw_number,
                status=status,
                reason_code=reason_code,
                history_cutoff_draw_number=cutoff_number,
                history_cutoff_draw_date=cutoff_date,
                native_generation=native_generation,
                native_tickets=native_tickets,
                ordered_portfolio=ordered_portfolio,
                portfolio_derivation=portfolio_derivation,
                candidate_k=candidate_k,
                combination_count=combination_count,
            )
        )
    return tuple(executions)


def _criterion_success(
    criterion: HistoricalPrefixSuccessCriterion,
    *,
    main_hits: int,
    special_hit: bool,
) -> bool:
    if criterion is HistoricalPrefixSuccessCriterion.M3_PLUS:
        return main_hits >= 3
    if criterion is HistoricalPrefixSuccessCriterion.M4_PLUS:
        return main_hits >= 4
    if criterion is HistoricalPrefixSuccessCriterion.M5_PLUS:
        return main_hits >= 5
    if criterion is HistoricalPrefixSuccessCriterion.M6:
        return main_hits == 6
    minimum = {
        HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL: 2,
        HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL: 3,
        HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL: 4,
        HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL: 5,
    }[criterion]
    return main_hits >= minimum and special_hit


def _render_fraction_decimal_18(value: Fraction) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    scale = 10**18
    rounded, remainder = divmod(absolute.numerator * scale, absolute.denominator)
    doubled = remainder * 2
    if doubled > absolute.denominator or (
        doubled == absolute.denominator and rounded % 2 == 1
    ):
        rounded += 1
    integer_part, fractional_part = divmod(rounded, scale)
    if rounded == 0:
        sign = ""
    return f"{sign}{integer_part}.{fractional_part:018d}"


def _exact_fraction_payload(value: Fraction) -> dict[str, int | str]:
    return {
        "decimal_18": _render_fraction_decimal_18(value),
        "denominator": value.denominator,
        "numerator": value.numerator,
    }


def _score_ticket(ticket: Ticket, target: _Target) -> tuple[int, bool, str]:
    main_hits = len(set(ticket) & set(target.winning_main_numbers))
    special_hit = target.winning_special_number in ticket
    resolution = resolve_big_lotto_prize_tier(main_hits, special_hit)
    if type(resolution) is BigLottoPrizeTier:
        prize = resolution.tier_id.value
    else:
        if resolution is not NoPrizeResult.NO_PRIZE:
            raise AssertionError("unexpected prize resolution")
        prize = NoPrizeResult.NO_PRIZE.value
    return main_hits, special_hit, prize


def _window_targets(
    targets: tuple[_Target, ...],
    requested_draws: int | None,
) -> tuple[_Target, ...]:
    if requested_draws is None:
        return targets
    return targets[-requested_draws:]


def evaluate_biglotto_multi_ticket_backtest(
    raw_input: bytes,
    *,
    catalog: FullStrategyCatalog | None = None,
) -> dict[str, object]:
    """Validate one artifact and return the complete-universe report payload."""

    try:
        parsed = json.loads(raw_input)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise MultiTicketBacktestInputError("input is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise MultiTicketBacktestInputError("input must be a JSON object")
    document = cast(dict[str, Any], parsed)
    if document.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise MultiTicketBacktestInputError("unsupported input schema_version")
    if document.get("lottery_type") != "BIG_LOTTO":
        raise MultiTicketBacktestInputError("lottery_type must be BIG_LOTTO")
    dataset_id = _required_text(document, "dataset_id", "input")
    dataset_version = _required_text(document, "dataset_version", "input")
    dataset_sha256 = _required_text(document, "dataset_sha256", "input")
    if len(dataset_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in dataset_sha256
    ):
        raise MultiTicketBacktestInputError("dataset_sha256 must be a lowercase SHA-256")
    source_provenance = document.get("source_provenance")
    if source_provenance is not None and not isinstance(source_provenance, dict):
        raise MultiTicketBacktestInputError(
            "source_provenance must be absent or an object"
        )

    active_catalog = catalog or load_full_strategy_catalog()
    targets = _parse_targets(document)
    executions = _parse_executions(
        document,
        catalog=active_catalog,
        targets=targets,
    )
    target_by_number = {target.draw_number: target for target in targets}
    successful_strategy_ids = {
        execution.strategy_id
        for execution in executions
        if execution.status is PortfolioExecutionStatus.OK
    }
    execution_audit: list[dict[str, object]] = []
    for execution in executions:
        audit_row: dict[str, object] = {
            "history_cutoff_draw_date": (
                execution.history_cutoff_draw_date.isoformat()
                if execution.history_cutoff_draw_date is not None
                else ""
            ),
            "history_cutoff_draw_number": (
                execution.history_cutoff_draw_number or ""
            ),
            "reason_code": execution.reason_code or "",
            "status": execution.status.value,
            "strategy_id": execution.strategy_id,
            "strategy_version": execution.strategy_version,
            "target_draw_number": execution.target_draw_number,
        }
        if execution.status is PortfolioExecutionStatus.OK:
            native_payload = [list(ticket) for ticket in execution.native_tickets]
            portfolio_payload = [
                list(ticket) for ticket in execution.ordered_portfolio
            ]
            audit_row.update(
                {
                    "candidate_k": execution.candidate_k or "",
                    "combination_count": execution.combination_count or "",
                    "native_duplicate_ticket_count": (
                        len(execution.native_tickets)
                        - len(set(execution.native_tickets))
                    ),
                    "native_ticket_count": len(execution.native_tickets),
                    "native_generation": execution.native_generation or {},
                    "native_tickets": native_payload,
                    "native_tickets_ordered_sha256": hashlib.sha256(
                        json.dumps(
                            native_payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "ordered_portfolio": portfolio_payload,
                    "ordered_portfolio_sha256": hashlib.sha256(
                        json.dumps(
                            portfolio_payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "portfolio_derivation": execution.portfolio_derivation or "",
                    "portfolio_duplicate_ticket_count": (
                        len(execution.ordered_portfolio)
                        - len(set(execution.ordered_portfolio))
                    ),
                    "portfolio_ticket_count": len(execution.ordered_portfolio),
                }
            )
        execution_audit.append(audit_row)

    metrics: list[dict[str, object]] = []
    official_metrics: list[dict[str, object]] = []
    prizes: list[dict[str, object]] = []
    metric_by_identity: dict[tuple[str, int, str, str], dict[str, object]] = {}
    official_metric_by_identity: dict[
        tuple[str, int, str], dict[str, object]
    ] = {}
    for record in active_catalog.records:
        strategy_executions = tuple(
            execution
            for execution in executions
            if execution.strategy_id == record.strategy_id
        )
        if not strategy_executions:
            continue
        for window_name, requested_draws in WINDOWS:
            selected_targets = _window_targets(targets, requested_draws)
            selected_target_ids = {target.draw_number for target in selected_targets}
            selected_executions = tuple(
                execution
                for execution in strategy_executions
                if execution.target_draw_number in selected_target_ids
            )
            successful = tuple(
                execution
                for execution in selected_executions
                if execution.status is PortfolioExecutionStatus.OK
            )
            window_target_count = len(selected_targets)
            execution_status_counts = Counter(
                execution.status.value for execution in selected_executions
            )
            execution_status_counts["MISSING_EXECUTION_RECORD"] = (
                window_target_count - len(selected_executions)
            )
            for prefix_count in PREFIX_COUNTS:
                prize_counts = Counter({tier.value: 0 for tier in BigLottoPrizeTierId})
                prize_counts[NoPrizeResult.NO_PRIZE.value] = 0
                duplicate_positions = 0
                distinct_positions = 0
                observations_with_duplicates = 0
                scored_by_execution: list[list[tuple[int, bool, str]]] = []
                for execution in successful:
                    selected_tickets = execution.ordered_portfolio[:prefix_count]
                    distinct = len(set(selected_tickets))
                    distinct_positions += distinct
                    duplicate_positions += prefix_count - distinct
                    observations_with_duplicates += int(distinct != prefix_count)
                    target = target_by_number[execution.target_draw_number]
                    ticket_scores = [
                        _score_ticket(ticket, target) for ticket in selected_tickets
                    ]
                    scored_by_execution.append(ticket_scores)
                    prize_counts.update(score[2] for score in ticket_scores)

                prizes.append(
                    {
                        "execution_count": len(successful),
                        "no_prize_count": prize_counts[NoPrizeResult.NO_PRIZE.value],
                        "observation_count_with_duplicate_tickets": (
                            observations_with_duplicates
                        ),
                        "observed_distinct_ticket_count": distinct_positions,
                        "observed_duplicate_ticket_count": duplicate_positions,
                        "official_prize_tier_counts": {
                            tier.value: prize_counts[tier.value]
                            for tier in BigLottoPrizeTierId
                        },
                        "prefix_count": prefix_count,
                        "strategy_id": record.strategy_id,
                        "ticket_position_count": len(successful) * prefix_count,
                        "window": window_name,
                        "window_available_draws": window_target_count,
                        "window_requested_draws": requested_draws or window_target_count,
                    }
                )

                observation_count = len(successful)
                official_any_prize_count = sum(
                    any(
                        prize != NoPrizeResult.NO_PRIZE.value
                        for _main_hits, _special_hit, prize in ticket_scores
                    )
                    for ticket_scores in scored_by_execution
                )
                official_any_prize_rate = (
                    Fraction(official_any_prize_count, observation_count)
                    if observation_count
                    else Fraction(0, 1)
                )
                official_baseline = official_any_prize_probability(prefix_count)
                official_baseline_fraction = official_baseline.as_fraction()
                official_rate_delta = (
                    official_any_prize_rate - official_baseline_fraction
                )
                official_fields: dict[str, object] = {
                    "official_any_prize_count": official_any_prize_count,
                    "official_any_prize_rate": _exact_fraction_payload(
                        official_any_prize_rate
                    ),
                    "official_random_baseline_probability": (
                        _exact_fraction_payload(official_baseline_fraction)
                    ),
                    "official_random_baseline_delta": _exact_fraction_payload(
                        official_rate_delta
                    ),
                }
                official_metric_payload: dict[str, object] = {
                    **official_fields,
                    "coverage": _exact_fraction_payload(
                        Fraction(observation_count, window_target_count)
                    ),
                    "criterion": "OFFICIAL_ANY_PRIZE",
                    "execution_status_counts": dict(
                        sorted(execution_status_counts.items())
                    ),
                    "prefix_count": prefix_count,
                    "rankable": observation_count > 0,
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "successful_execution_count": observation_count,
                    "window": window_name,
                    "window_available_draws": window_target_count,
                    "window_complete": (
                        requested_draws is None
                        or window_target_count == requested_draws
                    ),
                    "window_requested_draws": requested_draws or window_target_count,
                }
                official_metrics.append(official_metric_payload)
                official_metric_by_identity[
                    (record.strategy_id, prefix_count, window_name)
                ] = official_metric_payload

                for criterion in SUCCESS_CRITERIA:
                    success_count = sum(
                        any(
                            _criterion_success(
                                criterion,
                                main_hits=main_hits,
                                special_hit=special_hit,
                            )
                            for main_hits, special_hit, _prize in ticket_scores
                        )
                        for ticket_scores in scored_by_execution
                    )
                    observation_count = len(successful)
                    observed_rate = (
                        Fraction(success_count, observation_count)
                        if observation_count
                        else Fraction(0, 1)
                    )
                    baseline = portfolio_success_probability(criterion, prefix_count)
                    baseline_fraction = baseline.as_fraction()
                    rate_delta = observed_rate - baseline_fraction
                    coverage = Fraction(observation_count, window_target_count)
                    metric_payload: dict[str, object] = {
                        **official_fields,
                        "coverage": _exact_fraction_payload(coverage),
                        "criterion": criterion.value,
                        "exact_random_baseline_probability": (
                            _exact_fraction_payload(baseline_fraction)
                        ),
                        "execution_status_counts": dict(
                            sorted(execution_status_counts.items())
                        ),
                        "observed_success_count": success_count,
                        "observed_success_rate": _exact_fraction_payload(observed_rate),
                        "prefix_count": prefix_count,
                        "random_baseline_rate_difference": (
                            _exact_fraction_payload(rate_delta)
                        ),
                        "rankable": observation_count > 0,
                        "strategy_id": record.strategy_id,
                        "strategy_version": record.strategy_version,
                        "successful_execution_count": observation_count,
                        "window": window_name,
                        "window_available_draws": window_target_count,
                        "window_complete": (
                            requested_draws is None
                            or window_target_count == requested_draws
                        ),
                        "window_requested_draws": requested_draws or window_target_count,
                    }
                    metrics.append(metric_payload)
                    metric_by_identity[
                        (
                            record.strategy_id,
                            prefix_count,
                            window_name,
                            criterion.value,
                        )
                    ] = metric_payload

    universe: list[dict[str, object]] = []
    for record in active_catalog.records:
        if record.strategy_id in successful_strategy_ids:
            status = ReproductionStatus.BACKTESTED
            unranked_reason = ""
        else:
            status = record.reproduction_status
            unranked_reason = record.unranked_reason
        universe.append(
            {
                "duplicate_alias_target": record.duplicate_alias_target or "",
                "legacy_method_id": record.legacy_method_id,
                "reproduction_status": status.value,
                "source_commit": record.source_commit,
                "source_path": record.source_path,
                "source_sha256": record.source_sha256,
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "unranked_reason": unranked_reason,
            }
        )

    official_rankings: list[dict[str, object]] = []
    official_top_twenty: list[dict[str, object]] = []
    official_rank_by_identity: dict[tuple[str, int, str], int] = {}
    for prefix_count in PREFIX_COUNTS:
        for window_name, _requested_draws in WINDOWS:
            rankable: list[
                tuple[Fraction, Fraction, Fraction, str, dict[str, object]]
            ] = []
            for record in active_catalog.records:
                cell_metric = official_metric_by_identity.get(
                    (record.strategy_id, prefix_count, window_name)
                )
                if cell_metric is None or cell_metric["rankable"] is not True:
                    continue
                observed = cast(
                    dict[str, object], cell_metric["official_any_prize_rate"]
                )
                delta = cast(
                    dict[str, object], cell_metric["official_random_baseline_delta"]
                )
                coverage = cast(dict[str, object], cell_metric["coverage"])
                rankable.append(
                    (
                        Fraction(
                            cast(int, observed["numerator"]),
                            cast(int, observed["denominator"]),
                        ),
                        Fraction(
                            cast(int, delta["numerator"]),
                            cast(int, delta["denominator"]),
                        ),
                        Fraction(
                            cast(int, coverage["numerator"]),
                            cast(int, coverage["denominator"]),
                        ),
                        record.strategy_id,
                        cell_metric,
                    )
                )
            rankable.sort(
                key=lambda item: (-item[0], -item[1], -item[2], item[3])
            )
            rank_by_id = {
                item[3]: index for index, item in enumerate(rankable, start=1)
            }
            for record in active_catalog.records:
                cell_metric = official_metric_by_identity.get(
                    (record.strategy_id, prefix_count, window_name)
                )
                rank = rank_by_id.get(record.strategy_id)
                if rank is not None:
                    official_rank_by_identity[
                        (record.strategy_id, prefix_count, window_name)
                    ] = rank
                if cell_metric is None:
                    reason = (
                        "NO_EXECUTIONS_IN_THIS_REPORT_INPUT"
                        if record.reproduction_status is ReproductionStatus.BACKTESTED
                        else record.unranked_reason
                    )
                elif cell_metric["rankable"] is not True:
                    reason = "NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW"
                else:
                    reason = ""
                row: dict[str, object] = {
                    "criterion": "OFFICIAL_ANY_PRIZE",
                    "official_rank": rank or "",
                    "prefix_count": prefix_count,
                    "strategy_id": record.strategy_id,
                    "unranked_reason": reason,
                    "window": window_name,
                }
                if cell_metric is not None:
                    row.update(
                        {
                            "coverage": cell_metric["coverage"],
                            "official_any_prize_count": cell_metric[
                                "official_any_prize_count"
                            ],
                            "official_any_prize_rate": cell_metric[
                                "official_any_prize_rate"
                            ],
                            "official_random_baseline_probability": cell_metric[
                                "official_random_baseline_probability"
                            ],
                            "official_random_baseline_delta": cell_metric[
                                "official_random_baseline_delta"
                            ],
                        }
                    )
                official_rankings.append(row)
                if type(rank) is int and rank <= 20:
                    official_top_twenty.append(row)

    rankings: list[dict[str, object]] = []
    top_ten: list[dict[str, object]] = []
    for prefix_count in PREFIX_COUNTS:
        for window_name, _requested_draws in WINDOWS:
            for criterion in SUCCESS_CRITERIA:
                rankable: list[tuple[Fraction, Fraction, Fraction, str, dict[str, object]]] = []
                for record in active_catalog.records:
                    cell_metric = metric_by_identity.get(
                        (
                            record.strategy_id,
                            prefix_count,
                            window_name,
                            criterion.value,
                        )
                    )
                    if cell_metric is None or cell_metric["rankable"] is not True:
                        continue
                    observed = cast(
                        dict[str, object],
                        cell_metric["observed_success_rate"],
                    )
                    delta = cast(
                        dict[str, object],
                        cell_metric["random_baseline_rate_difference"],
                    )
                    coverage = cast(dict[str, object], cell_metric["coverage"])
                    rankable.append(
                        (
                            Fraction(
                                cast(int, observed["numerator"]),
                                cast(int, observed["denominator"]),
                            ),
                            Fraction(
                                cast(int, delta["numerator"]),
                                cast(int, delta["denominator"]),
                            ),
                            Fraction(
                                cast(int, coverage["numerator"]),
                                cast(int, coverage["denominator"]),
                            ),
                            record.strategy_id,
                            cell_metric,
                        )
                    )
                rankable.sort(
                    key=lambda item: (
                        -item[0],
                        -item[1],
                        -item[2],
                        item[3],
                    )
                )
                rank_by_id = {
                    item[3]: index for index, item in enumerate(rankable, start=1)
                }
                cell_rows: list[dict[str, object]] = []
                for record in active_catalog.records:
                    cell_metric = metric_by_identity.get(
                        (
                            record.strategy_id,
                            prefix_count,
                            window_name,
                            criterion.value,
                        )
                    )
                    rank = rank_by_id.get(record.strategy_id)
                    if cell_metric is None:
                        reason = (
                            "NO_EXECUTIONS_IN_THIS_REPORT_INPUT"
                            if record.reproduction_status
                            is ReproductionStatus.BACKTESTED
                            else record.unranked_reason
                        )
                    elif cell_metric["rankable"] is not True:
                        reason = "NO_SUCCESSFUL_EXECUTIONS_IN_WINDOW"
                    else:
                        reason = ""
                    row: dict[str, object] = {
                        "criterion": criterion.value,
                        "official_rank": official_rank_by_identity.get(
                            (record.strategy_id, prefix_count, window_name), ""
                        ),
                        "prefix_count": prefix_count,
                        "rank": rank or "",
                        "strategy_id": record.strategy_id,
                        "unranked_reason": reason,
                        "window": window_name,
                    }
                    if cell_metric is not None:
                        row["official_any_prize_count"] = cell_metric[
                            "official_any_prize_count"
                        ]
                        row["official_any_prize_rate"] = cell_metric[
                            "official_any_prize_rate"
                        ]
                        row["official_random_baseline_probability"] = (
                            cell_metric["official_random_baseline_probability"]
                        )
                        row["official_random_baseline_delta"] = cell_metric[
                            "official_random_baseline_delta"
                        ]
                        row["coverage"] = cell_metric["coverage"]
                        row["observed_success_rate"] = cell_metric[
                            "observed_success_rate"
                        ]
                        row["random_baseline_rate_difference"] = cell_metric[
                            "random_baseline_rate_difference"
                        ]
                    cell_rows.append(row)
                    rankings.append(row)
                top_ten.extend(
                    row
                    for row in cell_rows
                    if type(row["rank"]) is int and row["rank"] <= 10
                )

    backtested_strategy_ids = successful_strategy_ids | {
        record.strategy_id
        for record in active_catalog.records
        if record.reproduction_status is ReproductionStatus.BACKTESTED
    }
    backtested_count = len(backtested_strategy_ids)
    closed_count = sum(
        record.reproduction_status is ReproductionStatus.CLOSED_UNEXECUTABLE
        for record in active_catalog.records
        if record.strategy_id not in backtested_strategy_ids
    )
    alias_count = sum(
        record.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS
        for record in active_catalog.records
    )
    pending_count = sum(
        record.reproduction_status is ReproductionStatus.OWNER_DECISION_REQUIRED
        for record in active_catalog.records
        if record.strategy_id not in backtested_strategy_ids
    )
    progress = {
        "backtested_count": backtested_count,
        "closed_count": closed_count,
        "duplicate_alias_count": alias_count,
        "owner_decision_required_count": pending_count,
        "reproduced_count": backtested_count,
        "total_strategy_count": len(active_catalog.records),
        "uncompleted_count": pending_count,
    }
    canonical_input = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    report: dict[str, object] = {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "catalog_sha256": active_catalog.catalog_sha256,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "dataset_version": dataset_version,
        "execution_audit": execution_audit,
        "input_canonical_sha256": hashlib.sha256(canonical_input).hexdigest(),
        "input_raw_sha256": hashlib.sha256(raw_input).hexdigest(),
        "lottery_type": "BIG_LOTTO",
        "metrics": metrics,
        "official_metrics": official_metrics,
        "official_prize_distributions": prizes,
        "portfolio_contract": {
            "candidate_k_is_ticket_count": False,
            "combination_count_is_ticket_count": False,
            "prefix_counts": list(PREFIX_COUNTS),
            "same_ordered_20_portfolio_for_every_prefix": True,
        },
        "progress": progress,
        "rankings": rankings,
        "official_rankings": official_rankings,
        "official_top_20": official_top_twenty,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_provenance": source_provenance or {},
        "target_draw_count": len(targets),
        "top_10": top_ten,
        "universe": universe,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(
            report,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return report


__all__ = [
    "BACKTEST_POLICY_VERSION",
    "INPUT_SCHEMA_VERSION",
    "PREFIX_COUNTS",
    "REPORT_SCHEMA_VERSION",
    "RESEARCH_DISCLAIMER",
    "SUCCESS_CRITERIA",
    "WINDOWS",
    "MultiTicketBacktestInputError",
    "PortfolioExecutionStatus",
    "evaluate_biglotto_multi_ticket_backtest",
]
