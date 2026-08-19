#!/usr/bin/env python3
# ruff: noqa: E501, RUF001
"""Reproduce the B649 lagged physical-draw-order Level-1 falsification.

The source fixture is the verified Track A official ``month``/``endMonth``
snapshot.  This experiment keeps every historical six-number set fixed and
compares a small chronological selector keyed by set-only information plus
lagged physical-order features with two order placebos:

* within-draw order shuffled while preserving every six-number set; and
* deliberately stale order history.

Candidate tickets are produced only from canonical sorted winning-number sets.
The order signal can therefore change portfolio selection, but cannot change
the prediction budget or smuggle physical order into the candidate tickets.
The current target row is used only for scoring after prediction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import random
import shutil
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

TASK_ID = "B649_TRACK_B_LAGGED_PHYSICAL_DRAW_ORDER_LEVEL1_R1"
TARGET_MIN = 113000006
TARGET_MAX = 115000069
WARMUP_DRAWS = 200
ORDER_WINDOW = 30
STALE_LAG_DRAWS = 8
MIN_REGIME_OBSERVATIONS = 24
BLOCK_COUNT = 4
SEARCH_CONFIG_COUNT = 1
SHUFFLE_SEED = TASK_ID + ":ORDER_SHUFFLED_PLACEBO"
BASELINE_PORTFOLIO = "HORIZON_MINIMAX_2"
CANDIDATE_PORTFOLIOS = (
    "HORIZON_MINIMAX_2",
    "DEVIATION_2",
    "ZONE_SPLIT_2_OF_3",
)
SOURCE_ENDPOINT = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"

TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parents[1]
SOURCE_INPUT = (
    REPO_ROOT
    / ".task-data"
    / "B649_TRACK_A_DRAW_NUMBER_APPEAR_SEMANTIC_COVERAGE_VALIDATION_R1"
    / "fixtures"
    / "source_snapshot.json"
)
SOURCE_COPY = TASK_DIR / "source_snapshot.json"

sys.path.insert(0, str(REPO_ROOT / "src"))

from lottolab.domain.draws import LotteryType  # noqa: E402
from lottolab.strategies.adapters.base import CausalDrawRow  # noqa: E402
from lottolab.strategies.adapters.biglotto_horizon_minimax import (  # noqa: E402
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.adapters.biglotto_selected import (  # noqa: E402
    BigLottoDeviation2BetAdapter,
    BigLottoDeviation2BetBet2Adapter,
    BigLottoZoneSplit3BetBet1Adapter,
    BigLottoZoneSplit3BetBet2Adapter,
)

RawRow = dict[str, Any]


@dataclass(frozen=True, slots=True)
class DrawRow:
    period: int
    date: str
    numbers: tuple[int, ...]
    order: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PortfolioOutcome:
    tickets: tuple[tuple[int, ...], ...]
    ticket_hits: tuple[int, ...]
    m2_plus: bool
    m3_plus: bool
    average_matched_numbers: float


@dataclass(frozen=True, slots=True)
class TargetRecord:
    draw: str
    date: str
    source_row_index: int
    eligible_index: int
    benchmark_index: int | None
    year: int
    outcome: tuple[int, ...]
    candidates: dict[str, PortfolioOutcome]


@dataclass(frozen=True, slots=True)
class ConditionPoint:
    record: TargetRecord
    selected_portfolio: str
    outcome: PortfolioOutcome


@dataclass(frozen=True, slots=True)
class Summary:
    target_count: int
    tickets_per_target: int
    m2_plus_hits: int
    m2_plus_rate: float
    m3_plus_hits: int
    m3_plus_rate: float
    average_matched_numbers: float
    selected_portfolio_counts: dict[str, int]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def required_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    return cast(int, value)


def required_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def required_int_list(value: Any, label: str, length: int) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} values")
    values = tuple(required_int(item, label) for item in value)
    if len(set(values)) != length or any(value < 1 or value > 49 for value in values):
        raise ValueError(f"{label} must contain unique integers in 1..49")
    return values


def date_text(row: RawRow) -> str:
    value = row.get("lotteryDate")
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("lotteryDate must be an ISO-like string")
    result = value[:10]
    datetime.fromisoformat(result)
    return result


def materialize_source() -> dict[str, Any]:
    """Copy the verified source fixture once, then require byte stability."""

    if not SOURCE_INPUT.is_file():
        raise FileNotFoundError(f"verified Track A source fixture is absent: {SOURCE_INPUT}")
    input_bytes = SOURCE_INPUT.read_bytes()
    if not SOURCE_COPY.exists():
        shutil.copyfile(SOURCE_INPUT, SOURCE_COPY)
    if SOURCE_COPY.read_bytes() != input_bytes:
        raise ValueError("task-owned source_snapshot.json differs from the verified input fixture")
    payload = json.loads(input_bytes.decode("utf-8"))
    return required_mapping(payload, "source snapshot")


def load_rows(snapshot: dict[str, Any]) -> tuple[tuple[DrawRow, ...], dict[str, Any]]:
    raw_rows = snapshot.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("source snapshot rows must be a list")
    full_query = required_mapping(snapshot.get("full_query"), "full_query")
    if full_query != {"month": "2007-01", "endMonth": "2026-08"}:
        raise ValueError(f"unexpected official pagination query: {full_query}")
    full_pages = snapshot.get("full_pages")
    if not isinstance(full_pages, list) or len(full_pages) != 6:
        raise ValueError("source snapshot must retain six official pages")
    if required_int(snapshot.get("row_count"), "row_count") != 2161:
        raise ValueError("source snapshot row_count is not 2161")
    if len(raw_rows) != 2161:
        raise ValueError(f"source snapshot has {len(raw_rows)} rows, expected 2161")
    if any(required_int(page.get("total_size"), "page.total_size") != 2161 for page in full_pages):
        raise ValueError("official page total_size changed across the retained pages")
    if any(required_int(page.get("field_missing_rows"), "page.field_missing_rows") != 0 for page in full_pages):
        raise ValueError("the retained official pages contain missing drawNumberAppear fields")
    if sum(required_int(page.get("returned_rows"), "page.returned_rows") for page in full_pages) != 2161:
        raise ValueError("official page union does not equal the retained row count")

    seen_periods: set[int] = set()
    seen_dates: set[str] = set()
    rows: list[DrawRow] = []
    for index, raw_value in enumerate(raw_rows):
        raw = required_mapping(raw_value, f"source row {index}")
        period = required_int(raw.get("period"), f"source row {index}.period")
        draw_date = date_text(raw)
        if period in seen_periods or draw_date in seen_dates:
            raise ValueError(f"duplicate source identity at row {index}")
        seen_periods.add(period)
        seen_dates.add(draw_date)
        numbers_with_special = required_int_list(
            raw.get("drawNumberSize"), f"source row {index}.drawNumberSize", 7
        )
        order_with_special = required_int_list(
            raw.get("drawNumberAppear"), f"source row {index}.drawNumberAppear", 7
        )
        if set(numbers_with_special[:6]) != set(order_with_special[:6]):
            raise ValueError(f"source row {index} violates the number-set permutation invariant")
        if numbers_with_special[6] != order_with_special[6]:
            raise ValueError(f"source row {index} moves the special number out of slot 7")
        rows.append(
            DrawRow(
                period=period,
                date=draw_date,
                numbers=tuple(sorted(numbers_with_special[:6])),
                order=order_with_special[:6],
            )
        )
    ordered = tuple(sorted(rows, key=lambda row: (row.date, row.period)))
    if tuple(row.period for row in ordered) == tuple(row.period for row in rows):
        raise ValueError("source snapshot unexpectedly lost its official newest-first order")
    if tuple(row.date for row in ordered) != tuple(sorted(row.date for row in ordered)):
        raise ValueError("source rows are not chronologically sortable")
    metadata = {
        "source_endpoint": SOURCE_ENDPOINT,
        "query": full_query,
        "page_count": len(full_pages),
        "source_draw_count": len(ordered),
        "source_rows_sha256": sha256_hex(raw_rows),
        "first_draw": str(ordered[0].period),
        "last_draw": str(ordered[-1].period),
        "first_date": ordered[0].date,
        "last_date": ordered[-1].date,
    }
    return ordered, metadata


def to_causal_history(rows: tuple[DrawRow, ...]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(draw=str(row.period), date=row.date, numbers=row.numbers)
        for row in rows
    )


def single_ticket_portfolio(adapter: Any, history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    first, _special = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    return (first,)


def candidate_predictions(history: tuple[CausalDrawRow, ...]) -> dict[str, tuple[tuple[int, ...], ...]]:
    """Return the fixed two-ticket candidate set from sorted-number history only."""

    horizon = BigLottoHorizonMinimaxDisagreementAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    )
    deviation = (
        single_ticket_portfolio(BigLottoDeviation2BetAdapter(), history)[0],
        single_ticket_portfolio(BigLottoDeviation2BetBet2Adapter(), history)[0],
    )
    zone = (
        single_ticket_portfolio(BigLottoZoneSplit3BetBet1Adapter(), history)[0],
        single_ticket_portfolio(BigLottoZoneSplit3BetBet2Adapter(), history)[0],
    )
    result = {
        "HORIZON_MINIMAX_2": horizon,
        "DEVIATION_2": deviation,
        "ZONE_SPLIT_2_OF_3": zone,
    }
    if tuple(result) != CANDIDATE_PORTFOLIOS:
        raise AssertionError("candidate portfolio order drifted")
    if any(len(tickets) != 2 for tickets in result.values()):
        raise AssertionError("candidate portfolios do not preserve two tickets")
    return result


def score_portfolio(
    tickets: tuple[tuple[int, ...], ...], outcome: tuple[int, ...]
) -> PortfolioOutcome:
    outcome_set = set(outcome)
    hits = tuple(len(set(ticket) & outcome_set) for ticket in tickets)
    return PortfolioOutcome(
        tickets=tickets,
        ticket_hits=hits,
        m2_plus=any(hit >= 2 for hit in hits),
        m3_plus=any(hit >= 3 for hit in hits),
        average_matched_numbers=sum(hits) / len(hits),
    )


def build_records(
    rows: tuple[DrawRow, ...], benchmark_positions: dict[str, int]
) -> tuple[TargetRecord, ...]:
    records: list[TargetRecord] = []
    for row_index, row in enumerate(rows):
        if row_index < WARMUP_DRAWS:
            continue
        if row.period > TARGET_MAX:
            break
        history = to_causal_history(rows[:row_index])
        candidates = candidate_predictions(history)
        scored = {
            name: score_portfolio(tickets, row.numbers)
            for name, tickets in candidates.items()
        }
        draw = str(row.period)
        records.append(
            TargetRecord(
                draw=draw,
                date=row.date,
                source_row_index=row_index,
                eligible_index=len(records),
                benchmark_index=benchmark_positions.get(draw),
                year=int(row.date[:4]),
                outcome=row.numbers,
                candidates=scored,
            )
        )
    return tuple(records)


def deterministic_shuffle_order(order: tuple[int, ...], draw: str) -> tuple[int, ...]:
    digest = hashlib.sha256(f"{SHUFFLE_SEED}:{draw}".encode()).hexdigest()
    rng = random.Random(int(digest, 16))
    shuffled = list(order)
    rng.shuffle(shuffled)
    return tuple(shuffled)


def shuffled_rows(rows: tuple[DrawRow, ...]) -> tuple[DrawRow, ...]:
    result = tuple(
        replace(row, order=deterministic_shuffle_order(row.order, str(row.period)))
        for row in rows
    )
    for original, placebo in zip(rows, result, strict=True):
        if set(original.order) != set(placebo.order) or original.numbers != tuple(sorted(placebo.order)):
            raise AssertionError("ORDER_SHUFFLED_PLACEBO changed a historical number set")
    return result


def set_regime_key(history: tuple[DrawRow, ...]) -> str:
    """A low-cardinality set-only state, deliberately independent of order."""

    if len(history) < 2:
        return "SET_MISSING"
    overlap = len(set(history[-1].numbers) & set(history[-2].numbers))
    return f"SET_OVERLAP_{min(overlap, 3)}"


def bucket_front_low(value: float) -> str:
    if value < 1.35:
        return "LOW"
    if value > 1.65:
        return "HIGH"
    return "BALANCED"


def bucket_adjacency(value: float) -> str:
    if value < 0.16:
        return "LOW"
    if value > 0.24:
        return "HIGH"
    return "BALANCED"


def order_feature_values(history: tuple[tuple[int, ...], ...]) -> tuple[str, str, str]:
    """Return bounded positional-recency and adjacency buckets from prior order."""

    recent = history[-ORDER_WINDOW:]
    if not recent:
        return "MISSING", "MISSING", "ORDER_MISSING"
    front_low_values = [sum(number <= 24 for number in order[:3]) for order in recent]
    adjacency_rates = [
        sum(abs(left - right) == 1 for left, right in itertools.pairwise(order)) / 5
        for order in recent
    ]
    front_bucket = bucket_front_low(statistics.fmean(front_low_values))
    adjacency_bucket = bucket_adjacency(statistics.fmean(adjacency_rates))
    return (
        front_bucket,
        adjacency_bucket,
        f"ORDER_FRONT_{front_bucket}|ORDER_ADJ_{adjacency_bucket}",
    )


def key_series(
    records: tuple[TargetRecord, ...],
    canonical_rows: tuple[DrawRow, ...],
    order_rows: tuple[DrawRow, ...],
    *,
    stale: bool = False,
) -> tuple[tuple[str, str, str], ...]:
    keys: list[tuple[str, str, str]] = []
    for record in records:
        index = record.source_row_index
        set_key = set_regime_key(canonical_rows[:index])
        order_index = max(0, index - STALE_LAG_DRAWS) if stale else index
        order_history = tuple(row.order for row in order_rows[:order_index])
        front_bucket, adjacency_bucket, order_key = order_feature_values(order_history)
        keys.append((set_key, order_key, f"{set_key}|{order_key}"))
        if front_bucket == "MISSING" or adjacency_bucket == "MISSING":
            keys[-1] = (set_key, "ORDER_MISSING", f"{set_key}|ORDER_MISSING")
    return tuple(keys)


def combined_key_series(
    records: tuple[TargetRecord, ...],
    canonical_rows: tuple[DrawRow, ...],
    order_rows: tuple[DrawRow, ...],
    *,
    stale: bool = False,
) -> tuple[str, ...]:
    return tuple(
        combined
        for _set_key, _order_key, combined in key_series(
            records, canonical_rows, order_rows, stale=stale
        )
    )


def set_only_key_series(
    records: tuple[TargetRecord, ...], canonical_rows: tuple[DrawRow, ...]
) -> tuple[str, ...]:
    return tuple(
        set_regime_key(canonical_rows[: record.source_row_index]) for record in records
    )


def candidate_metric(record: TargetRecord, candidate: str) -> float:
    return float(record.candidates[candidate].m2_plus)


def fit_selector(
    records: tuple[TargetRecord, ...], keys: tuple[str, ...], before_index: int
) -> tuple[dict[str, str], dict[str, int]]:
    if len(records) != len(keys):
        raise AssertionError("selector inputs are not aligned")
    by_key: dict[str, list[TargetRecord]] = {}
    for index, key in enumerate(keys[:before_index]):
        by_key.setdefault(key, []).append(records[index])
    mapping: dict[str, str] = {}
    counts: dict[str, int] = {}
    for key, training_records in by_key.items():
        counts[key] = len(training_records)
        if key.endswith("MISSING") or len(training_records) < MIN_REGIME_OBSERVATIONS:
            mapping[key] = BASELINE_PORTFOLIO
            continue
        means = {
            candidate: statistics.fmean(
                candidate_metric(record, candidate) for record in training_records
            )
            for candidate in CANDIDATE_PORTFOLIOS
        }
        mapping[key] = min(
            CANDIDATE_PORTFOLIOS,
            key=lambda candidate: (
                -means[candidate],
                0 if candidate == BASELINE_PORTFOLIO else 1,
                candidate,
            ),
        )
    return mapping, counts


def run_selector(
    records: tuple[TargetRecord, ...], keys: tuple[str, ...]
) -> tuple[tuple[ConditionPoint, ...], Counter[str], int]:
    points: list[ConditionPoint] = []
    selected_counts: Counter[str] = Counter()
    fallback_count = 0
    for index, record in enumerate(records):
        mapping, counts = fit_selector(records, keys, index)
        key = keys[index]
        selected = mapping.get(key, BASELINE_PORTFOLIO)
        if key.endswith("MISSING") or counts.get(key, 0) < MIN_REGIME_OBSERVATIONS:
            fallback_count += 1
        selected_counts[selected] += 1
        points.append(ConditionPoint(record, selected, record.candidates[selected]))
    return tuple(points), selected_counts, fallback_count


def benchmark_records(records: tuple[TargetRecord, ...]) -> tuple[TargetRecord, ...]:
    selected = tuple(record for record in records if record.benchmark_index is not None)
    if not selected:
        raise ValueError("development benchmark is empty")
    actual = [cast(int, record.benchmark_index) for record in selected]
    if actual != list(range(len(selected))):
        raise AssertionError("benchmark positions are not chronological and contiguous")
    return selected


def benchmark_blocks(
    benchmark: tuple[TargetRecord, ...],
) -> tuple[tuple[str, tuple[TargetRecord, ...]], ...]:
    blocks: list[tuple[str, tuple[TargetRecord, ...]]] = []
    for block_index in range(BLOCK_COUNT):
        start = (block_index * len(benchmark)) // BLOCK_COUNT
        end = ((block_index + 1) * len(benchmark)) // BLOCK_COUNT
        block = benchmark[start:end]
        if not block:
            raise AssertionError("chronological benchmark block is empty")
        blocks.append((f"DEV_W{block_index + 1}", block))
    return tuple(blocks)


def summary(points: tuple[ConditionPoint, ...], target_draws: set[str]) -> Summary:
    selected = tuple(point for point in points if point.record.draw in target_draws)
    if not selected:
        raise ValueError("summary target set is empty")
    m2 = sum(point.outcome.m2_plus for point in selected)
    m3 = sum(point.outcome.m3_plus for point in selected)
    return Summary(
        target_count=len(selected),
        tickets_per_target=2,
        m2_plus_hits=m2,
        m2_plus_rate=m2 / len(selected),
        m3_plus_hits=m3,
        m3_plus_rate=m3 / len(selected),
        average_matched_numbers=statistics.fmean(
            point.outcome.average_matched_numbers for point in selected
        ),
        selected_portfolio_counts=dict(Counter(point.selected_portfolio for point in selected)),
    )


def decision(
    baseline: Summary,
    set_only: Summary,
    real: Summary,
    shuffled: Summary,
    stale: Summary,
    block_deltas: tuple[float, ...],
) -> dict[str, Any]:
    real_delta = real.m2_plus_rate - baseline.m2_plus_rate
    set_only_delta = set_only.m2_plus_rate - baseline.m2_plus_rate
    incremental_delta = real.m2_plus_rate - set_only.m2_plus_rate
    positive_blocks = sum(delta > 0 for delta in block_deltas)
    nonnegative_blocks = sum(delta >= 0 for delta in block_deltas)
    chronological_stable = positive_blocks >= 2 and nonnegative_blocks >= 3
    beats_all_controls = (
        real.m2_plus_rate > baseline.m2_plus_rate
        and real.m2_plus_rate > shuffled.m2_plus_rate
        and real.m2_plus_rate > stale.m2_plus_rate
    )
    survives_set_only = incremental_delta > 0
    advance = beats_all_controls and chronological_stable and survives_set_only
    if not real.m2_plus_rate > shuffled.m2_plus_rate:
        status = "NO_SIGNAL"
    elif advance:
        status = "ADVANCE"
    elif real_delta > 0:
        status = "WEAK_SIGNAL"
    else:
        status = "NO_SIGNAL"
    return {
        "status": status,
        "action": "ADVANCE" if advance else "DO_NOT_ADVANCE",
        "real_delta_m2_plus": real_delta,
        "set_only_delta_m2_plus": set_only_delta,
        "incremental_delta": incremental_delta,
        "positive_blocks": positive_blocks,
        "nonnegative_blocks": nonnegative_blocks,
        "chronological_stable": chronological_stable,
        "beats_baseline": real.m2_plus_rate > baseline.m2_plus_rate,
        "beats_shuffled": real.m2_plus_rate > shuffled.m2_plus_rate,
        "beats_stale": real.m2_plus_rate > stale.m2_plus_rate,
        "survives_set_only": survives_set_only,
        "advance": advance,
    }


def write_csv(path: Path, header: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def rate(value: float) -> str:
    return f"{value:.4f}"


def order_feature_rows(
    records: tuple[TargetRecord, ...],
    canonical_rows: tuple[DrawRow, ...],
    real_rows: tuple[DrawRow, ...],
    shuffled: tuple[DrawRow, ...],
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    variants = (
        ("REAL", real_rows, False),
        ("ORDER_SHUFFLED_PLACEBO", shuffled, False),
        ("STALE_ORDER_PLACEBO", real_rows, True),
    )
    for variant, source_rows, stale in variants:
        values: list[tuple[str, str, str]] = []
        for record in records:
            index = record.source_row_index
            order_index = max(0, index - STALE_LAG_DRAWS) if stale else index
            values.append(order_feature_values(tuple(row.order for row in source_rows[:order_index])))
        for feature_index, feature_name in enumerate(
            ("front_low_position_bucket", "adjacency_bucket", "combined_order_key")
        ):
            feature_values = [value[feature_index] for value in values]
            rows.append(
                (
                    variant,
                    "POSITIONAL_RECENCY" if feature_index == 0 else "POSITIONAL_PAIR_ADJACENCY" if feature_index == 1 else "ORDER_COMBINED",
                    feature_name,
                    ORDER_WINDOW,
                    len(set(feature_values)),
                    sum(value == "MISSING" or value == "ORDER_MISSING" for value in feature_values),
                    json.dumps(dict(Counter(feature_values)), sort_keys=True),
                    "derived only from historical order strictly before the target; stale variant omits the latest 8 eligible draws",
                )
            )
    set_values = [
        set_regime_key(canonical_rows[: record.source_row_index]) for record in records
    ]
    rows.append(
        (
            "SET_ONLY_CONTROL",
            "NUMBER_SET",
            "last_draw_set_overlap_bucket",
            "last 2 historical canonical sets",
            len(set(set_values)),
            sum(value == "SET_MISSING" for value in set_values),
            json.dumps(dict(Counter(set_values)), sort_keys=True),
            "order-invariant control feature; canonical sorted winning-number sets only",
        )
    )
    return rows


def render_report(
    *,
    metadata: dict[str, Any],
    benchmark: tuple[TargetRecord, ...],
    summaries: dict[str, Summary],
    block_summaries: dict[str, dict[str, Summary]],
    decision_record: dict[str, Any],
    selector_stats: dict[str, tuple[Counter[str], int]],
) -> str:
    baseline = summaries["BASELINE_ONLY"]
    set_only = summaries["SET_ONLY_CONTROL"]
    real = summaries["BASELINE_PLUS_REAL_ORDER"]
    shuffled = summaries["ORDER_SHUFFLED_PLACEBO"]
    stale = summaries["STALE_ORDER_PLACEBO"]
    condition_order = (
        "BASELINE_ONLY",
        "SET_ONLY_CONTROL",
        "BASELINE_PLUS_REAL_ORDER",
        "ORDER_SHUFFLED_PLACEBO",
        "STALE_ORDER_PLACEBO",
    )
    condition_lines = []
    for condition in condition_order:
        current = summaries[condition]
        condition_lines.append(
            f"| {condition} | {current.m2_plus_hits}/{current.target_count} | "
            f"{rate(current.m2_plus_rate)} | {current.m3_plus_hits}/{current.target_count} | "
            f"{rate(current.m3_plus_rate)} | {current.average_matched_numbers:.4f} | "
            f"{rate(current.m2_plus_rate - baseline.m2_plus_rate)} |"
        )
    block_lines = []
    for block_name, block_summary in block_summaries.items():
        block_lines.append(
            f"| {block_name} | {block_summary['BASELINE_ONLY'].target_count} | "
            f"{rate(block_summary['BASELINE_ONLY'].m2_plus_rate)} | "
            f"{rate(block_summary['SET_ONLY_CONTROL'].m2_plus_rate)} | "
            f"{rate(block_summary['BASELINE_PLUS_REAL_ORDER'].m2_plus_rate)} | "
            f"{rate(block_summary['ORDER_SHUFFLED_PLACEBO'].m2_plus_rate)} | "
            f"{rate(block_summary['STALE_ORDER_PLACEBO'].m2_plus_rate)} |"
        )
    selector_lines = "\n".join(
        f"- `{name}`: fallbacks `{fallbacks}`, selected `{dict(counts)}`"
        for name, (counts, fallbacks) in selector_stats.items()
    )
    positive_blocks = decision_record["positive_blocks"]
    return f"""# {TASK_ID}

TASK_ID: `{TASK_ID}`  
STATUS: **COMPLETE — {decision_record['status']} / {decision_record['action']}**  
TARGET_COUNT: **{len(benchmark)}**  
DEVELOPMENT_WINDOWS: **DEV_W1–DEV_W4**, chronological; common benchmark `{benchmark[0].draw}`–`{benchmark[-1].draw}`  
COMMON_DEVELOPMENT_BENCHMARK: **YES**  
CLEAN_HELD_OUT_CONFIRMATION: **NO**

## Final fields

PHYSICAL_ORDER_SOURCE: `{metadata['source_endpoint']}`, verified Track A `drawNumberAppear` source fixture  
SOURCE_DRAW_COUNT: **{metadata['source_draw_count']}**  
JOINED_DRAW_COUNT: **2160/2161 exact period join; 2160/2160 date-aligned join** (reused Track A read-only local-snapshot evidence)  
ANALYSIS_SOURCE_ROWS_CONSUMED: **{metadata['source_draw_count']}/{metadata['source_draw_count']}**  
BASELINE_METHOD: **HORIZON_MINIMAX_2**, two fixed tickets from canonical set-only history  
BASELINE_M2_PLUS: **{baseline.m2_plus_hits}/{baseline.target_count} ({rate(baseline.m2_plus_rate)})**  
REAL_ORDER_M2_PLUS: **{real.m2_plus_hits}/{real.target_count} ({rate(real.m2_plus_rate)})**  
DELTA_VS_BASELINE: **{rate(real.m2_plus_rate - baseline.m2_plus_rate)}**  
ORDER_SHUFFLED_PLACEBO_M2_PLUS: **{shuffled.m2_plus_hits}/{shuffled.target_count} ({rate(shuffled.m2_plus_rate)})**  
REAL_MINUS_ORDER_SHUFFLED: **{rate(real.m2_plus_rate - shuffled.m2_plus_rate)}**  
STALE_ORDER_PLACEBO_M2_PLUS: **{stale.m2_plus_hits}/{stale.target_count} ({rate(stale.m2_plus_rate)})**  
REAL_MINUS_STALE: **{rate(real.m2_plus_rate - stale.m2_plus_rate)}**  
SET_ONLY_CONTROL_M2_PLUS: **{set_only.m2_plus_hits}/{set_only.target_count} ({rate(set_only.m2_plus_rate)})**  
ORDER_INCREMENTAL_DELTA: **{rate(real.m2_plus_rate - set_only.m2_plus_rate)}**  
M3_PLUS_RESULTS: **baseline {baseline.m3_plus_hits}/{baseline.target_count} ({rate(baseline.m3_plus_rate)}); real {real.m3_plus_hits}/{real.target_count} ({rate(real.m3_plus_rate)}); shuffled {shuffled.m3_plus_hits}/{shuffled.target_count} ({rate(shuffled.m3_plus_rate)}); stale {stale.m3_plus_hits}/{stale.target_count} ({rate(stale.m3_plus_rate)})**  
POSITIVE_CHRONOLOGICAL_BLOCKS: **{positive_blocks}/{BLOCK_COUNT}**  
SEARCH_CONFIG_COUNT: **{SEARCH_CONFIG_COUNT}**  
SEARCH_OVERFIT_RISK: **MODERATE CAVEAT — the final decision uses one initial locked configuration; a post-result threshold sensitivity was run and explicitly invalidated under the no-rescue rule**  
SIGNAL_CLASSIFICATION: **{decision_record['status']}**  
DECISION: **{decision_record['action']}**  
KEY_LESSONS: **Real order improves over the fixed baseline but loses to the
order-shuffled placebo and the set-only control; the observed lift is not
incremental physical-order information.**  
NEXT: **Close the physical-order line and return to D fallback EH27.**  
REPO_MUTATION: **task data only**  
DB_MUTATION: **NONE**

## Authority and source coverage

Track A's verified semantic authority classifies `drawNumberAppear` as
`PHYSICAL_DRAW_ORDER`, with a permutation invariant and no malformed or
duplicate rows. The retained official source fixture has `{metadata['source_draw_count']}`
rows, six pages, `totalSize=2161` on each page, and zero missing order fields.
Its pagination method is the official `month`/`endMonth` query, not the
provider-shaped `startMonth` broad request.

PHYSICAL_ORDER_SEMANTIC_AUTHORITY: **PASS**  
HISTORICAL_SOURCE_COVERAGE: **PASS**  
PAGINATION_METHOD: **MONTH_ENDMONTH**  
SOURCE_ROWS_SHA256: `{metadata['source_rows_sha256']}`

## Model and controls

All candidate tickets are created from `drawNumberSize[:6]`, sorted as
canonical number sets. `SET_ONLY_CONTROL` is a low-cardinality selector keyed
by the overlap of the two latest historical number sets. The primary real
model adds two locked order-derived buckets: the recent share of low numbers
in physical positions 1–3 (`POSITIONAL_RECENCY`) and the recent rate of
consecutive-number adjacency in physical neighbor positions
(`POSITIONAL_PAIR_ADJACENCY`). The selector is fit only on strictly earlier
records and falls back to the baseline until a key has `{MIN_REGIME_OBSERVATIONS}`
earlier observations.

`ORDER_SHUFFLED_PLACEBO` deterministically permutes only the six main physical
positions within each historical draw. The exact six-number set and the
two-ticket exposure remain unchanged. `STALE_ORDER_PLACEBO` uses the same
order features after removing the latest `{STALE_LAG_DRAWS}` eligible historical
draws. Neither placebo changes the candidate generation or target scoring.

| Condition | M2+ | M2+ rate | M3+ | M3+ rate | Avg matched | Δ vs baseline |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(condition_lines)}

## Chronological blocks

| Block | Targets | Baseline | Set-only | Real order | Shuffled order | Stale order |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(block_lines)}

Real order was positive in `{positive_blocks}` blocks and non-negative in
`{decision_record['nonnegative_blocks']}` blocks. This is descriptive evidence
inside the exposed development benchmark, not prospective confirmation.

## Causal and reproducibility gates

NO_FUTURE_LEAKAGE: **PASS** — order and set keys read only rows strictly before
each target; target outcomes are read only after candidate prediction for
scoring.  
CURRENT_TARGET_ORDER_USED: **NO**  
SAME_NUMBER_SET_CONTROL: **PASS** — canonical candidate history and shuffled
placebo retain identical six-number sets.  
ORDER_SHUFFLED_PLACEBO: **PASS** — deterministic within-draw six-position
permutation completed for all `{metadata['source_draw_count']}` source rows.  
EQUAL_EXPOSURE: **PASS** — every condition scores exactly two tickets for each
of `{len(benchmark)}` targets.  
REPRODUCTION: **PASS** — the script reads the task-owned source copy and
regenerates all CSV/Markdown artifacts offline.  

Selector diagnostics:

{selector_lines}

## Attempt ledger

- **Attempt 1 — initial locked configuration:** completed offline; baseline
  79 M2+, real order 91, shuffled placebo 98, stale placebo 92, set-only 92;
  result `NO_SIGNAL / DO_NOT_ADVANCE`.
- **Attempt 2 — identical reproduction:** completed offline with byte-identical
  artifacts.
- **Attempt 3 — superseded sensitivity:** changing the fixed adjacency bucket
  cutoffs from `<0.16/>0.24` to `<0.03/>0.06` after observing Attempt 1
  produced baseline 79, real order 103, shuffled 84, stale 94, and set-only
  92. This branch is **invalidated and not used** because the packet forbids
  rescuing a failed result by retuning on the exposed benchmark.
- **Attempt 4 — restored final configuration:** the initial `<0.16/>0.24`
  thresholds were restored and the final artifacts were regenerated; the
  final decision remains `NO_SIGNAL / DO_NOT_ADVANCE`.

No production database, schema, ingestion path, production strategy
registration, or Strategy Matrix was changed. The prescribed next step is
`D fallback EH27` because this is **{decision_record['action']}**.

## Artifacts

- `report.md`
- `results.csv`
- `config_ledger.csv`
- `placebo_results.csv`
- `order_feature_summary.csv`
- `source_snapshot.json`
- `reproduce_analysis.py`
"""


def analyze(snapshot: dict[str, Any]) -> dict[str, Any]:
    rows, metadata = load_rows(snapshot)
    target_draws = {
        str(row.period) for row in rows if TARGET_MIN <= row.period <= TARGET_MAX
    }
    benchmark_positions = {draw: index for index, draw in enumerate(sorted(target_draws, key=int))}
    records = build_records(rows, benchmark_positions)
    benchmark = benchmark_records(records)
    benchmark_draws = {record.draw for record in benchmark}
    if len(benchmark_draws) != len(target_draws):
        missing = sorted(target_draws - benchmark_draws, key=int)
        raise ValueError(f"eligible records miss benchmark targets: {missing[:5]}")

    shuffled = shuffled_rows(rows)
    set_keys = set_only_key_series(records, rows)
    real_keys = combined_key_series(records, rows, rows)
    shuffled_keys = combined_key_series(records, rows, shuffled)
    stale_keys = combined_key_series(records, rows, rows, stale=True)

    baseline_points = tuple(
        ConditionPoint(record, BASELINE_PORTFOLIO, record.candidates[BASELINE_PORTFOLIO])
        for record in records
    )
    set_points, set_selected, set_fallbacks = run_selector(records, set_keys)
    real_points, real_selected, real_fallbacks = run_selector(records, real_keys)
    shuffled_points, shuffled_selected, shuffled_fallbacks = run_selector(records, shuffled_keys)
    stale_points, stale_selected, stale_fallbacks = run_selector(records, stale_keys)
    all_points = {
        "BASELINE_ONLY": baseline_points,
        "SET_ONLY_CONTROL": set_points,
        "BASELINE_PLUS_REAL_ORDER": real_points,
        "ORDER_SHUFFLED_PLACEBO": shuffled_points,
        "STALE_ORDER_PLACEBO": stale_points,
    }
    summaries = {
        name: summary(points, benchmark_draws) for name, points in all_points.items()
    }
    block_summaries: dict[str, dict[str, Summary]] = {}
    for block_name, block_records in benchmark_blocks(benchmark):
        block_draws = {record.draw for record in block_records}
        block_summaries[block_name] = {
            name: summary(points, block_draws) for name, points in all_points.items()
        }
    block_deltas = tuple(
        block_summaries[name]["BASELINE_PLUS_REAL_ORDER"].m2_plus_rate
        - block_summaries[name]["BASELINE_ONLY"].m2_plus_rate
        for name in block_summaries
    )
    decision_record = decision(
        summaries["BASELINE_ONLY"],
        summaries["SET_ONLY_CONTROL"],
        summaries["BASELINE_PLUS_REAL_ORDER"],
        summaries["ORDER_SHUFFLED_PLACEBO"],
        summaries["STALE_ORDER_PLACEBO"],
        block_deltas,
    )

    results_rows: list[tuple[Any, ...]] = []
    condition_notes = {
        "BASELINE_ONLY": "Existing Horizon Minimax two-ticket producer; set-only candidate history.",
        "SET_ONLY_CONTROL": "Same candidates and chronological selector keyed only by canonical set overlap.",
        "BASELINE_PLUS_REAL_ORDER": "Set-only key plus locked lagged physical-order positional/adjacency key.",
        "ORDER_SHUFFLED_PLACEBO": "Same selector after deterministic within-draw order shuffle; six-number sets fixed.",
        "STALE_ORDER_PLACEBO": f"Same selector using order history {STALE_LAG_DRAWS} eligible draws stale.",
    }
    for condition, points in all_points.items():
        windows: list[tuple[str, set[str], str, str]] = [
            ("COMMON_DEVELOPMENT_BENCHMARK", benchmark_draws, benchmark[0].draw, benchmark[-1].draw)
        ]
        windows.extend(
            (block_name, {record.draw for record in block}, block[0].draw, block[-1].draw)
            for block_name, block in benchmark_blocks(benchmark)
        )
        for window_name, window_draws, draw_start, draw_end in windows:
            current = summary(points, window_draws)
            baseline_window = summary(baseline_points, window_draws)
            results_rows.append(
                (
                    condition,
                    condition.lower(),
                    window_name,
                    draw_start,
                    draw_end,
                    current.target_count,
                    current.tickets_per_target,
                    current.m2_plus_hits,
                    rate(current.m2_plus_rate),
                    current.m3_plus_hits,
                    rate(current.m3_plus_rate),
                    f"{current.average_matched_numbers:.4f}",
                    rate(current.m2_plus_rate - baseline_window.m2_plus_rate),
                    json.dumps(current.selected_portfolio_counts, sort_keys=True),
                    condition_notes[condition],
                )
            )

    baseline = summaries["BASELINE_ONLY"]
    placebo_rows = [
        (
            condition,
            current.target_count,
            current.tickets_per_target,
            current.m2_plus_hits,
            rate(current.m2_plus_rate),
            current.m3_plus_hits,
            rate(current.m3_plus_rate),
            f"{current.average_matched_numbers:.4f}",
            rate(current.m2_plus_rate - baseline.m2_plus_rate),
            json.dumps(current.selected_portfolio_counts, sort_keys=True),
        )
        for condition, current in summaries.items()
    ]

    config_rows = [
        (TASK_ID, "C01", "DATA_AUTHORITY", "Track A official source_snapshot.json", "LOCKED", metadata["source_rows_sha256"]),
        (TASK_ID, "C02", "TARGET_POPULATION", f"{TARGET_MIN}-{TARGET_MAX}", "LOCKED", "300-target common development benchmark"),
        (TASK_ID, "C03", "PAGINATION", "month/endMonth; six pages; pageSize=400", "PASS", "official query retained in source fixture"),
        (TASK_ID, "C04", "BASELINE", BASELINE_PORTFOLIO, "LOCKED", "two tickets; sorted number-set history"),
        (TASK_ID, "C05", "CANDIDATE_SET", ";".join(CANDIDATE_PORTFOLIOS), "LOCKED", "three same-budget two-ticket portfolios"),
        (TASK_ID, "C06", "SET_ONLY_CONTROL", "last-draw set-overlap bucket", "LOCKED", "order-invariant"),
        (
            TASK_ID,
            "C07",
            "REAL_ORDER_FEATURE",
            "30-draw front-low positional bucket + adjacency bucket",
            "LOCKED",
            "front-low <1.35/>1.65; adjacency <0.16/>0.24; no target row read",
        ),
        (TASK_ID, "C08", "ORDER_SHUFFLED_PLACEBO", f"SHA-256 deterministic within-draw shuffle seed {SHUFFLE_SEED}", "PASS", "six-number set preserved"),
        (TASK_ID, "C09", "STALE_ORDER_PLACEBO", f"order history stale by {STALE_LAG_DRAWS} eligible draws", "LOCKED", "same selector and candidate budget"),
        (TASK_ID, "C10", "SELECTOR", f"chronological M2+ regime lookup; min observations={MIN_REGIME_OBSERVATIONS}", "LOCKED", "strictly earlier records only"),
        (TASK_ID, "C11", "EXPOSURE", "2 tickets per target for all conditions", "PASS", "same target population and scoring"),
        (TASK_ID, "C12", "SEARCH_CONFIG_COUNT", str(SEARCH_CONFIG_COUNT), "PASS", "one locked configuration; no benchmark rescue"),
        (TASK_ID, "C13", "NO_FUTURE_LEAKAGE", "order/set keys from rows strictly before target", "PASS", "target outcomes only after prediction"),
        (TASK_ID, "C14", "CURRENT_TARGET_ORDER", "NO", "PASS", "current draw order never enters features"),
        (TASK_ID, "C15", "DB_MUTATION", "NONE", "PASS", "task-owned files only"),
    ]
    feature_rows = order_feature_rows(records, rows, rows, shuffled)
    selector_stats = {
        "SET_ONLY_CONTROL": (set_selected, set_fallbacks),
        "BASELINE_PLUS_REAL_ORDER": (real_selected, real_fallbacks),
        "ORDER_SHUFFLED_PLACEBO": (shuffled_selected, shuffled_fallbacks),
        "STALE_ORDER_PLACEBO": (stale_selected, stale_fallbacks),
    }
    report = render_report(
        metadata=metadata,
        benchmark=benchmark,
        summaries=summaries,
        block_summaries=block_summaries,
        decision_record=decision_record,
        selector_stats=selector_stats,
    )

    write_csv(
        TASK_DIR / "results.csv",
        (
            "condition",
            "model_variant",
            "window",
            "draw_start",
            "draw_end",
            "target_count",
            "tickets_per_target",
            "m2_plus_hits",
            "m2_plus_rate",
            "m3_plus_hits",
            "m3_plus_rate",
            "average_matched_numbers",
            "delta_m2_plus_rate_vs_same_window_baseline",
            "selected_portfolio_counts",
            "notes",
        ),
        results_rows,
    )
    write_csv(
        TASK_DIR / "placebo_results.csv",
        (
            "condition",
            "target_count",
            "tickets_per_target",
            "m2_plus_hits",
            "m2_plus_rate",
            "m3_plus_hits",
            "m3_plus_rate",
            "average_matched_numbers",
            "delta_m2_plus_rate_vs_baseline",
            "selected_portfolio_counts",
        ),
        placebo_rows,
    )
    write_csv(
        TASK_DIR / "config_ledger.csv",
        ("task_id", "config_id", "component", "setting", "status", "evidence"),
        config_rows,
    )
    write_csv(
        TASK_DIR / "order_feature_summary.csv",
        (
            "variant",
            "feature_family",
            "feature_name",
            "window_draws",
            "value_cardinality",
            "missing_count",
            "value_counts",
            "notes",
        ),
        feature_rows,
    )
    (TASK_DIR / "report.md").write_text(report, encoding="utf-8")
    return {
        "metadata": metadata,
        "benchmark": benchmark,
        "summaries": summaries,
        "decision": decision_record,
        "results_rows": results_rows,
        "config_rows": config_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="reserved for an already verified bounded source fixture; default is Track A evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.source is not None and args.source.resolve() != SOURCE_INPUT.resolve():
        raise SystemExit("only the verified Track A source fixture is authorized for this task")
    snapshot = materialize_source()
    result = analyze(snapshot)
    decision_record = cast(dict[str, Any], result["decision"])
    summaries = cast(dict[str, Summary], result["summaries"])
    print(
        json.dumps(
            {
                "task_id": TASK_ID,
                "status": decision_record["status"],
                "decision": decision_record["action"],
                "target_count": summaries["BASELINE_ONLY"].target_count,
                "baseline_m2_plus": summaries["BASELINE_ONLY"].m2_plus_hits,
                "real_order_m2_plus": summaries["BASELINE_PLUS_REAL_ORDER"].m2_plus_hits,
                "order_shuffled_m2_plus": summaries["ORDER_SHUFFLED_PLACEBO"].m2_plus_hits,
                "stale_order_m2_plus": summaries["STALE_ORDER_PLACEBO"].m2_plus_hits,
                "set_only_control_m2_plus": summaries["SET_ONLY_CONTROL"].m2_plus_hits,
                "output_root": str(TASK_DIR),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
