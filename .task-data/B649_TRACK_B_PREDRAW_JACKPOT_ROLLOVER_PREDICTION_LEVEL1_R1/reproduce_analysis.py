"""Reproduce the Level-1 B649 pre-draw jackpot/rollover falsification.

The experiment is intentionally small.  It evaluates the existing two-ticket
Horizon Minimax producer against a bounded regime selector over three existing
two-ticket candidate portfolios.  The selector is trained only on strictly
earlier targets and uses the pre-draw jackpot state derived from the immediately
prior official metadata row.  Stale and time-shuffled feature series are run
through the identical selector and score path as causal placebos.

The first run must use ``--refresh`` to acquire the official metadata snapshot.
Later runs are offline and read ``official_metadata.json``.  The snapshot is
kept in this task directory so the report is reproducible even if the source
API changes after this task.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode


TASK_ID = "B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1"
TARGET_MIN = 113000006
TARGET_MAX = 115000069
SOURCE_ENDPOINT = (
    "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"
)
SOURCE_PAGE_SIZE = 400
SOURCE_START_MONTH = "2007-01"
SOURCE_END_MONTH = "2026-08"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
STALE_LAG_DRAWS = 8
MIN_REGIME_OBSERVATIONS = 24
BLOCK_COUNT = 4
SHUFFLE_SEED = "B649_TRACK_B_PREDRAW_JACKPOT_ROLLOVER_PREDICTION_LEVEL1_R1"
BASELINE_PORTFOLIO = "HORIZON_MINIMAX_2"
CANDIDATE_PORTFOLIOS = (
    "HORIZON_MINIMAX_2",
    "DEVIATION_2",
    "ZONE_SPLIT_2_OF_3",
)
PRIMARY_MODEL_KEY = "state_amount_bucket"
REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = TASK_DIR / "official_metadata.json"

sys.path.insert(0, str(REPO_ROOT))

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
class JackpotFeatures:
    """Only prior-row official jackpot fields exposed to the model."""

    target_draw: str
    target_date: str
    source_draw: str | None
    source_date: str | None
    pre_draw_rollover_amount: int | None
    rollover_state: str
    prior_jackpot_winner_count: int | None
    prior_jackpot_prize: int | None
    prior_jackpot_last_prize: int | None
    prior_jackpot_per_prize: int | None


@dataclass(frozen=True, slots=True)
class PortfolioOutcome:
    tickets: tuple[tuple[int, ...], ...]
    ticket_hits: tuple[int, ...]
    m2_plus: bool
    m3_plus: bool
    average_matched_numbers: float
    maximum_matched_numbers: int


@dataclass(frozen=True, slots=True)
class TargetRecord:
    draw: str
    date: str
    source_row_index: int
    eligible_index: int
    benchmark_index: int | None
    year: int
    feature: JackpotFeatures
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
    maximum_matched_numbers_average: float
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


def _curl_json(page_number: int) -> dict[str, Any]:
    query = urlencode(
        {
            "pageNum": page_number,
            "pageSize": SOURCE_PAGE_SIZE,
            "startMonth": SOURCE_START_MONTH,
            "endMonth": SOURCE_END_MONTH,
        }
    )
    url = f"{SOURCE_ENDPOINT}?{query}"
    command = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        "60",
        "-H",
        "Accept: application/json",
        "-H",
        "User-Agent: LottoLab/0.1 (+draw-sync)",
        "-H",
        "Origin: https://www.taiwanlottery.com",
        "-H",
        "Referer: https://www.taiwanlottery.com/",
        url,
    ]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"official metadata request failed for page {page_number}: {detail}")
    if len(completed.stdout) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"official metadata response exceeded {MAX_RESPONSE_BYTES} bytes")
    payload = json.loads(completed.stdout.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("official metadata response must be an object")
    result = cast(dict[str, Any], payload)
    if result.get("rtCode") != 0:
        raise RuntimeError(f"official metadata API returned rtCode={result.get('rtCode')!r}")
    return result


def refresh_snapshot() -> None:
    """Fetch the official rich payload once and persist an offline snapshot."""

    first_payload = _curl_json(1)
    first_content = required_mapping(first_payload.get("content"), "content")
    reported_total = required_int(first_content.get("totalSize"), "content.totalSize")
    rows_by_period: dict[int, RawRow] = {}
    page_number = 1
    while True:
        payload = first_payload if page_number == 1 else _curl_json(page_number)
        content = required_mapping(payload.get("content"), "content")
        raw_rows = content.get("lotto649Res")
        if not isinstance(raw_rows, list):
            raise ValueError(f"page {page_number} is missing content.lotto649Res")
        page_rows = cast(list[Any], raw_rows)
        if not page_rows:
            break
        for raw_row in page_rows:
            row = required_mapping(raw_row, "lotto649Res row")
            period = required_int(row.get("period"), "period")
            previous = rows_by_period.get(period)
            if previous is not None and canonical_bytes(previous) != canonical_bytes(row):
                raise ValueError(f"duplicate period {period} has conflicting payloads")
            rows_by_period[period] = row
        if len(rows_by_period) >= reported_total:
            break
        page_number += 1
        if page_number > math.ceil(reported_total / SOURCE_PAGE_SIZE) + 1:
            raise ValueError("pagination exceeded the reported official row count")

    if len(rows_by_period) != reported_total:
        raise ValueError(
            f"official metadata row count {len(rows_by_period)} != reported {reported_total}"
        )

    rows = [rows_by_period[period] for period in sorted(rows_by_period)]
    snapshot = {
        "schema_version": "b649-official-rich-metadata-snapshot-v1",
        "source_endpoint": SOURCE_ENDPOINT,
        "query": {
            "startMonth": SOURCE_START_MONTH,
            "endMonth": SOURCE_END_MONTH,
            "pageSize": SOURCE_PAGE_SIZE,
            "pages": page_number,
        },
        "retrieved_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reported_total_size": reported_total,
        "rows_sha256": sha256_hex(rows),
        "rows": rows,
    }
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_snapshot() -> tuple[dict[str, Any], tuple[RawRow, ...]]:
    if not SNAPSHOT_PATH.is_file():
        raise FileNotFoundError(
            f"{SNAPSHOT_PATH} is absent; run reproduce_analysis.py --refresh once"
        )
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snapshot = required_mapping(payload, "snapshot")
    rows_raw = snapshot.get("rows")
    if not isinstance(rows_raw, list):
        raise ValueError("snapshot.rows must be a list")
    rows = tuple(required_mapping(row, "snapshot row") for row in cast(list[Any], rows_raw))
    if snapshot.get("rows_sha256") != sha256_hex(rows):
        raise ValueError("snapshot rows_sha256 does not match the saved raw rows")
    return snapshot, rows


def _iso_date(row: RawRow) -> str:
    value = row.get("lotteryDate")
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("lotteryDate must be an ISO-like string")
    date_text = value[:10]
    datetime.fromisoformat(date_text)
    return date_text


def _validate_rich_rows(rows: tuple[RawRow, ...], reported_total: int) -> tuple[RawRow, ...]:
    if len(rows) != reported_total:
        raise ValueError(f"snapshot rows {len(rows)} != reported total {reported_total}")

    required_top_level = (
        "period",
        "lotteryDate",
        "drawNumberSize",
        "drawNumberAppear",
        "totalAmount",
        "sellAmount",
        "jackpotAssign",
    )
    jackpot_fields = ("prize", "lastPrize", "winnerCount", "perPrize")
    seen_periods: set[int] = set()
    seen_dates: set[str] = set()
    normalized: list[RawRow] = []
    for index, row in enumerate(rows):
        missing = [name for name in required_top_level if name not in row]
        if missing:
            raise ValueError(f"row {index} missing official fields: {missing}")
        period = required_int(row["period"], f"row {index}.period")
        draw_date = _iso_date(row)
        if period in seen_periods or draw_date in seen_dates:
            raise ValueError(f"duplicate official draw identity at row {index}")
        seen_periods.add(period)
        seen_dates.add(draw_date)

        numbers = row.get("drawNumberSize")
        appears = row.get("drawNumberAppear")
        if not isinstance(numbers, list) or len(numbers) != 7:
            raise ValueError(f"row {index}.drawNumberSize must contain 7 numbers")
        if not isinstance(appears, list) or len(appears) != 7:
            raise ValueError(f"row {index}.drawNumberAppear must contain 7 numbers")
        numbers_int = [required_int(value, f"row {index}.drawNumberSize") for value in numbers]
        appears_int = [required_int(value, f"row {index}.drawNumberAppear") for value in appears]
        if len(set(numbers_int)) != 7 or any(not 1 <= value <= 49 for value in numbers_int):
            raise ValueError(f"row {index}.drawNumberSize is not a valid 6+1 draw")
        if sorted(numbers_int) != sorted(appears_int):
            raise ValueError(f"row {index}.drawNumberAppear is not a number permutation")

        jackpot = required_mapping(row.get("jackpotAssign"), f"row {index}.jackpotAssign")
        for field in jackpot_fields:
            value = required_int(jackpot.get(field), f"row {index}.jackpotAssign.{field}")
            if value < 0:
                raise ValueError(f"row {index}.jackpotAssign.{field} is negative")

        normalized.append(row)

    ordered = tuple(
        sorted(
            normalized,
            key=lambda row: (_iso_date(row), required_int(row["period"], "period")),
        )
    )
    if tuple(_iso_date(row) for row in ordered) != tuple(sorted(_iso_date(row) for row in ordered)):
        raise ValueError("official rows are not chronologically ordered")
    return ordered


def rollover_chain_diagnostics(
    rows: tuple[RawRow, ...],
) -> tuple[int, int, tuple[str, ...]]:
    """Validate the prior-row rollover arithmetic without feeding target fields to the model."""

    checks = 0
    exact = 0
    mismatches: list[str] = []
    for prior, current in zip(rows, rows[1:]):
        prior_jackpot = required_mapping(prior["jackpotAssign"], "prior.jackpotAssign")
        if required_int(prior_jackpot["winnerCount"], "prior winnerCount") != 0:
            continue
        checks += 1
        expected = required_int(prior_jackpot["lastPrize"], "prior lastPrize") + required_int(
            prior_jackpot["prize"], "prior prize"
        )
        current_jackpot = required_mapping(current["jackpotAssign"], "current.jackpotAssign")
        actual = required_int(current_jackpot["lastPrize"], "current lastPrize")
        if expected == actual:
            exact += 1
        else:
            mismatches.append(
                f"{draw_number(prior)}->{draw_number(current)} expected={expected} actual={actual}"
            )
    return checks, exact, tuple(mismatches)


def main_numbers(row: RawRow) -> tuple[int, ...]:
    numbers = cast(list[Any], row["drawNumberSize"])
    return tuple(sorted(required_int(value, "drawNumberSize") for value in numbers[:6]))


def draw_number(row: RawRow) -> str:
    return str(required_int(row["period"], "period"))


def derive_pre_draw_jackpot_rollover(
    rows: tuple[RawRow, ...], target_row_index: int
) -> JackpotFeatures:
    """Derive target-t pre-draw state from row t-1 only.

    The current target row is deliberately not read here.  When the prior row
    had no jackpot winner, the entering rollover amount is the source-semantic
    ``prior.lastPrize + prior.prize``.  After a prior jackpot winner the amount
    remains missing rather than being silently converted to zero; the state is
    still observed as a reset/no-rollover regime.
    """

    target = rows[target_row_index]
    target_draw = draw_number(target)
    target_date = _iso_date(target)
    if target_row_index == 0:
        return JackpotFeatures(
            target_draw,
            target_date,
            None,
            None,
            None,
            "MISSING",
            None,
            None,
            None,
            None,
        )

    prior = rows[target_row_index - 1]
    prior_draw = draw_number(prior)
    prior_date = _iso_date(prior)
    if not (prior_date < target_date or (prior_date == target_date and int(prior_draw) < int(target_draw))):
        raise ValueError(f"target {target_draw} does not have a strictly prior source row")
    jackpot = required_mapping(prior["jackpotAssign"], "prior.jackpotAssign")
    winner_count = required_int(jackpot.get("winnerCount"), "prior winnerCount")
    prize = required_int(jackpot.get("prize"), "prior prize")
    last_prize = required_int(jackpot.get("lastPrize"), "prior lastPrize")
    per_prize = required_int(jackpot.get("perPrize"), "prior perPrize")
    if winner_count == 0:
        amount: int | None = last_prize + prize
        state = "ROLLOVER"
    else:
        amount = None
        state = "NO_ROLLOVER_RESET"
    return JackpotFeatures(
        target_draw,
        target_date,
        prior_draw,
        prior_date,
        amount,
        state,
        winner_count,
        prize,
        last_prize,
        per_prize,
    )


def history_for(rows: tuple[RawRow, ...], target_row_index: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=draw_number(row),
            date=_iso_date(row),
            numbers=main_numbers(row),
        )
        for row in rows[:target_row_index]
    )


def single_ticket_portfolio(adapter: Any, history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    first, _special = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    return (first,)


def candidate_predictions(history: tuple[CausalDrawRow, ...]) -> dict[str, tuple[tuple[int, ...], ...]]:
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
        raise AssertionError("candidate portfolio does not preserve the two-ticket budget")
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
        maximum_matched_numbers=max(hits),
    )


def build_records(
    rows: tuple[RawRow, ...],
    benchmark_positions: dict[str, int],
) -> tuple[TargetRecord, ...]:
    records: list[TargetRecord] = []
    for row_index, row in enumerate(rows):
        period = required_int(row["period"], "period")
        if row_index < 200:
            continue
        history = history_for(rows, row_index)
        candidates = candidate_predictions(history)
        outcome = main_numbers(row)
        scored = {
            name: score_portfolio(tickets, outcome)
            for name, tickets in candidates.items()
        }
        draw = draw_number(row)
        feature = derive_pre_draw_jackpot_rollover(rows, row_index)
        if feature.target_draw != draw:
            raise AssertionError("feature target identity drifted")
        records.append(
            TargetRecord(
                draw=draw,
                date=_iso_date(row),
                source_row_index=row_index,
                eligible_index=len(records),
                benchmark_index=benchmark_positions.get(draw),
                year=int(_iso_date(row)[:4]),
                feature=feature,
                candidates=scored,
            )
        )
        if period >= TARGET_MAX and draw not in benchmark_positions:
            # The loop still validates later rows if present, but avoids doing
            # unnecessary strategy work after the requested benchmark.
            break
    return tuple(records)


def build_amount_state_keys(
    pairs: tuple[tuple[str, int | None], ...],
) -> tuple[str, ...]:
    """Build a causal state+amount bucket using only earlier pairs."""

    prior_amounts: list[int] = []
    keys: list[str] = []
    for state, amount in pairs:
        if state == "MISSING":
            keys.append("MISSING")
            continue
        if amount is None:
            keys.append("NO_ROLLOVER_RESET")
            continue
        if not prior_amounts:
            keys.append("ROLLOVER")
        else:
            median = statistics.median(prior_amounts)
            keys.append("ROLLOVER_HIGH" if amount >= median else "ROLLOVER_LOW")
        prior_amounts.append(amount)
    return tuple(keys)


def deterministic_shuffle_pairs(
    pairs: tuple[tuple[str, int | None], ...], records: tuple[TargetRecord, ...]
) -> tuple[tuple[str, int | None], ...]:
    if len(pairs) != len(records):
        raise AssertionError("shuffle inputs are not aligned")
    order = sorted(
        range(len(pairs)),
        key=lambda index: hashlib.sha256(
            f"{SHUFFLE_SEED}:{records[index].draw}".encode("utf-8")
        ).hexdigest(),
    )
    shuffled = tuple(pairs[index] for index in order)
    if Counter(shuffled) != Counter(pairs):
        raise AssertionError("shuffled placebo does not preserve feature marginal distribution")
    return shuffled


def stale_pairs(
    pairs: tuple[tuple[str, int | None], ...], lag: int
) -> tuple[tuple[str, int | None], ...]:
    missing = ("MISSING", None)
    return tuple(pairs[index - lag] if index >= lag else missing for index in range(len(pairs)))


def state_only_keys(records: tuple[TargetRecord, ...]) -> tuple[str, ...]:
    return tuple(record.feature.rollover_state for record in records)


def year_keys(records: tuple[TargetRecord, ...]) -> tuple[str, ...]:
    return tuple(f"YEAR_{record.year}" for record in records)


def _candidate_metric(record: TargetRecord, candidate: str) -> float:
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
        if key == "MISSING" or len(training_records) < MIN_REGIME_OBSERVATIONS:
            mapping[key] = BASELINE_PORTFOLIO
            continue
        means = {
            candidate: statistics.fmean(
                _candidate_metric(record, candidate) for record in training_records
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
        if key == "MISSING" or counts.get(key, 0) < MIN_REGIME_OBSERVATIONS:
            fallback_count += 1
        selected_counts[selected] += 1
        points.append(
            ConditionPoint(record, selected, record.candidates[selected])
        )
    return tuple(points), selected_counts, fallback_count


def benchmark_records(records: tuple[TargetRecord, ...]) -> tuple[TargetRecord, ...]:
    selected = tuple(record for record in records if record.benchmark_index is not None)
    if not selected:
        raise ValueError("target benchmark is empty")
    expected = list(range(len(selected)))
    actual = [cast(int, record.benchmark_index) for record in selected]
    if actual != expected:
        raise AssertionError("benchmark positions are not contiguous")
    return selected


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
        maximum_matched_numbers_average=statistics.fmean(
            point.outcome.maximum_matched_numbers for point in selected
        ),
        selected_portfolio_counts=dict(Counter(point.selected_portfolio for point in selected)),
    )


def benchmark_blocks(benchmark: tuple[TargetRecord, ...]) -> tuple[tuple[str, tuple[TargetRecord, ...]], ...]:
    n = len(benchmark)
    blocks: list[tuple[str, tuple[TargetRecord, ...]]] = []
    for block_index in range(BLOCK_COUNT):
        start = (block_index * n) // BLOCK_COUNT
        end = ((block_index + 1) * n) // BLOCK_COUNT
        blocks.append((f"DEV_W{block_index + 1}", benchmark[start:end]))
    if any(not block_records for _name, block_records in blocks):
        raise AssertionError("chronological benchmark block is empty")
    return tuple(blocks)


def write_csv(path: Path, header: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def fmt_rate(value: float) -> str:
    return f"{value:.4f}"


def decision(
    baseline: Summary,
    real: Summary,
    stale: Summary,
    shuffled: Summary,
    era: Summary,
    block_deltas: tuple[float, ...],
) -> dict[str, Any]:
    delta = real.m2_plus_rate - baseline.m2_plus_rate
    stale_delta = stale.m2_plus_rate - baseline.m2_plus_rate
    shuffled_delta = shuffled.m2_plus_rate - baseline.m2_plus_rate
    era_delta = era.m2_plus_rate - baseline.m2_plus_rate
    required_hit_delta = max(2, math.ceil(baseline.target_count * 0.01))
    meaningful = (
        real.m2_plus_hits - baseline.m2_plus_hits >= required_hit_delta
        and delta >= 0.01
    )
    stable_positive_blocks = sum(value > 0 for value in block_deltas)
    stable_nonnegative_blocks = sum(value >= 0 for value in block_deltas)
    stable = stable_positive_blocks >= 2 and stable_nonnegative_blocks >= 3
    beats_placebos = (
        real.m2_plus_rate > stale.m2_plus_rate
        and real.m2_plus_rate > shuffled.m2_plus_rate
    )
    era_survives = delta > era_delta + 0.005
    advance = meaningful and stable and beats_placebos and era_survives
    status = "ADVANCE" if advance else ("WEAK_SIGNAL" if delta > 0 else "NO_SIGNAL")
    return {
        "status": status,
        "action": "ADVANCE" if advance else "DO_NOT_ADVANCE",
        "real_delta_m2_plus": delta,
        "stale_delta_m2_plus": stale_delta,
        "shuffled_delta_m2_plus": shuffled_delta,
        "era_delta_m2_plus": era_delta,
        "required_hit_delta": required_hit_delta,
        "meaningful_improvement": meaningful,
        "stable_positive_blocks": stable_positive_blocks,
        "stable_nonnegative_blocks": stable_nonnegative_blocks,
        "chronological_stability": stable,
        "beats_stale_placebo": real.m2_plus_rate > stale.m2_plus_rate,
        "beats_shuffled_placebo": real.m2_plus_rate > shuffled.m2_plus_rate,
        "era_control_survives": era_survives,
        "advance": advance,
    }


def analyze(snapshot: dict[str, Any], rows: tuple[RawRow, ...]) -> dict[str, Any]:
    reported_total = required_int(snapshot.get("reported_total_size"), "reported_total_size")
    ordered_rows = _validate_rich_rows(rows, reported_total)
    chain_checks, chain_exact, chain_mismatches = rollover_chain_diagnostics(ordered_rows)
    target_draws = {
        draw_number(row)
        for row in ordered_rows
        if TARGET_MIN <= required_int(row["period"], "period") <= TARGET_MAX
    }
    benchmark_position = {draw: index for index, draw in enumerate(sorted(target_draws, key=int))}
    records = build_records(ordered_rows, benchmark_position)
    benchmark = benchmark_records(records)
    benchmark_draws = {record.draw for record in benchmark}
    if len(benchmark_draws) != len(target_draws):
        missing = sorted(target_draws - benchmark_draws, key=int)
        raise ValueError(f"eligible records miss benchmark targets: {missing[:5]}")

    real_pairs = tuple(
        (record.feature.rollover_state, record.feature.pre_draw_rollover_amount)
        for record in records
    )
    stale_pair_series = stale_pairs(real_pairs, STALE_LAG_DRAWS)
    shuffled_pair_series = deterministic_shuffle_pairs(real_pairs, records)
    real_amount_keys = build_amount_state_keys(real_pairs)
    stale_amount_keys = build_amount_state_keys(stale_pair_series)
    shuffled_amount_keys = build_amount_state_keys(shuffled_pair_series)
    real_state_keys = state_only_keys(records)
    era_keys = year_keys(records)

    baseline_points = tuple(
        ConditionPoint(record, BASELINE_PORTFOLIO, record.candidates[BASELINE_PORTFOLIO])
        for record in records
    )
    real_points, _real_selected, real_fallback = run_selector(records, real_amount_keys)
    state_points, _state_selected, state_fallback = run_selector(records, real_state_keys)
    stale_points, _stale_selected, stale_fallback = run_selector(records, stale_amount_keys)
    shuffled_points, _shuffled_selected, shuffled_fallback = run_selector(
        records, shuffled_amount_keys
    )
    era_points, _era_selected, era_fallback = run_selector(records, era_keys)

    all_points = {
        "BASELINE_ONLY": baseline_points,
        "BASELINE_PLUS_ROLLOVER": real_points,
        "STATE_ONLY_SENSITIVITY": state_points,
        "STALE_PLACEBO": stale_points,
        "SHUFFLED_PLACEBO": shuffled_points,
        "ERA_CONTROL": era_points,
    }
    summaries = {
        name: summary(points, benchmark_draws) for name, points in all_points.items()
    }
    real_summary = summaries["BASELINE_PLUS_ROLLOVER"]
    block_summaries: dict[str, dict[str, Summary]] = {}
    for block_name, block_records in benchmark_blocks(benchmark):
        block_draws = {record.draw for record in block_records}
        block_summaries[block_name] = {
            name: summary(points, block_draws) for name, points in all_points.items()
        }
    block_deltas = tuple(
        block_summaries[name]["BASELINE_PLUS_ROLLOVER"].m2_plus_rate
        - block_summaries[name]["BASELINE_ONLY"].m2_plus_rate
        for name in block_summaries
    )
    decision_record = decision(
        summaries["BASELINE_ONLY"],
        real_summary,
        summaries["STALE_PLACEBO"],
        summaries["SHUFFLED_PLACEBO"],
        summaries["ERA_CONTROL"],
        block_deltas,
    )

    feature_rows: list[tuple[Any, ...]] = []
    for record in benchmark:
        feature = record.feature
        feature_rows.append(
            (
                record.draw,
                record.date,
                feature.source_draw or "",
                feature.source_date or "",
                "" if feature.pre_draw_rollover_amount is None else feature.pre_draw_rollover_amount,
                feature.rollover_state,
                "" if feature.prior_jackpot_winner_count is None else feature.prior_jackpot_winner_count,
                "" if feature.prior_jackpot_prize is None else feature.prior_jackpot_prize,
                "" if feature.prior_jackpot_last_prize is None else feature.prior_jackpot_last_prize,
                "" if feature.prior_jackpot_per_prize is None else feature.prior_jackpot_per_prize,
                record.year,
                f"DEV_W{(cast(int, record.benchmark_index) * BLOCK_COUNT) // len(benchmark) + 1}",
            )
        )

    results_rows: list[tuple[Any, ...]] = []
    baseline_overall = summaries["BASELINE_ONLY"]
    model_variants = {
        "BASELINE_ONLY": "baseline",
        "BASELINE_PLUS_ROLLOVER": PRIMARY_MODEL_KEY,
        "STATE_ONLY_SENSITIVITY": "state_only",
        "STALE_PLACEBO": "state_amount_bucket_stale",
        "SHUFFLED_PLACEBO": "state_amount_bucket_shuffled",
        "ERA_CONTROL": "calendar_year_control",
    }
    condition_notes = {
        "BASELINE_ONLY": "Existing Horizon Minimax producer; no jackpot feature.",
        "BASELINE_PLUS_ROLLOVER": (
            "Causal state+amount bucket selector; M2+ fit; strictly prior training."
        ),
        "STATE_ONLY_SENSITIVITY": "Causal rollover/no-rollover state-only sensitivity.",
        "STALE_PLACEBO": f"Same selector with {STALE_LAG_DRAWS}-draw stale state+amount pairs.",
        "SHUFFLED_PLACEBO": "Same selector with deterministic target-shuffled feature pairs.",
        "ERA_CONTROL": "Same selector keyed only by calendar year as a recent-era control.",
    }
    for condition, points in all_points.items():
        windows: list[tuple[str, set[str], str, str]] = [
            (
                "COMMON_DEVELOPMENT_BENCHMARK",
                benchmark_draws,
                benchmark[0].draw,
                benchmark[-1].draw,
            )
        ]
        windows.extend(
            (
                block_name,
                {record.draw for record in block_records},
                block_records[0].draw,
                block_records[-1].draw,
            )
            for block_name, block_records in benchmark_blocks(benchmark)
        )
        for window_name, window_draws, draw_start, draw_end in windows:
            current = summary(points, window_draws)
            baseline_window = summary(baseline_points, window_draws)
            results_rows.append(
                (
                    condition,
                    model_variants[condition],
                    window_name,
                    draw_start,
                    draw_end,
                    current.target_count,
                    current.tickets_per_target,
                    current.m2_plus_hits,
                    fmt_rate(current.m2_plus_rate),
                    current.m3_plus_hits,
                    fmt_rate(current.m3_plus_rate),
                    f"{current.average_matched_numbers:.4f}",
                    f"{current.m2_plus_rate - baseline_window.m2_plus_rate:.4f}",
                    json.dumps(current.selected_portfolio_counts, sort_keys=True),
                    condition_notes[condition],
                )
            )

    placebo_rows: list[tuple[Any, ...]] = []
    for condition in ("BASELINE_ONLY", "BASELINE_PLUS_ROLLOVER", "STALE_PLACEBO", "SHUFFLED_PLACEBO", "ERA_CONTROL"):
        current = summaries[condition]
        placebo_rows.append(
            (
                condition,
                current.target_count,
                current.tickets_per_target,
                current.m2_plus_hits,
                fmt_rate(current.m2_plus_rate),
                current.m3_plus_hits,
                fmt_rate(current.m3_plus_rate),
                f"{current.average_matched_numbers:.4f}",
                f"{current.m2_plus_rate - baseline_overall.m2_plus_rate:.4f}",
                json.dumps(current.selected_portfolio_counts, sort_keys=True),
            )
        )

    snapshot_rows_sha256 = str(snapshot["rows_sha256"])
    config_rows = [
        (TASK_ID, "C01", "DATA_AUTHORITY", "official rich Lotto649 API snapshot", "LOCKED", snapshot_rows_sha256),
        (TASK_ID, "C02", "TARGET_POPULATION", f"{TARGET_MIN}-{TARGET_MAX}", "LOCKED", "common development benchmark; not clean confirmation"),
        (TASK_ID, "C03", "BASELINE", BASELINE_PORTFOLIO, "LOCKED", "current operational Horizon Minimax 2-ticket producer"),
        (TASK_ID, "C04", "CANDIDATE_PORTFOLIOS", ";".join(CANDIDATE_PORTFOLIOS), "LOCKED", "three already-landed two-ticket candidates"),
        (TASK_ID, "C05", "PRIMARY_FEATURE", "prior winner/reset state + prior lastPrize + prior prize; amount=lastPrize+prize only after prior winnerCount=0", "LOCKED", "state_amount_bucket; target row jackpot fields excluded"),
        (TASK_ID, "C06", "PRIMARY_SELECTOR", f"regime lookup; M2+ fit; min observations={MIN_REGIME_OBSERVATIONS}", "LOCKED", "strictly chronological training"),
        (TASK_ID, "C07", "STATE_SENSITIVITY", "rollover/no-rollover state-only selector", "LOCKED", f"fallbacks={state_fallback}"),
        (TASK_ID, "C08", "STALE_PLACEBO", f"lag={STALE_LAG_DRAWS} eligible draws", "LOCKED", f"fallbacks={stale_fallback}"),
        (TASK_ID, "C09", "SHUFFLED_PLACEBO", f"deterministic pair shuffle seed={SHUFFLE_SEED}", "LOCKED", f"fallbacks={shuffled_fallback}"),
        (TASK_ID, "C10", "ERA_CONTROL", "calendar-year regime lookup", "LOCKED", f"fallbacks={era_fallback}"),
        (TASK_ID, "C11", "EXPOSURE", "2 tickets per target for every condition", "LOCKED", "equal exposure and prediction budget"),
        (TASK_ID, "C12", "DECISION_THRESHOLD", "meaningful = >=3 hits and >=1 percentage point M2+ improvement for this 300-target benchmark", "LOCKED", "max(2, ceil(target_count*0.01)); no post-benchmark retuning"),
        (TASK_ID, "C13", "CONFIGURATION_COUNT", "14 ledger rows; 6 evaluated conditions; 3 candidate portfolios", "PASS", "well below <=24 Level-1 budget"),
        (TASK_ID, "C14", "SOURCE_CHAIN_DIAGNOSTIC", f"{chain_exact}/{chain_checks} prior no-winner rollover transitions exact", "PASS_WITH_CAVEAT" if chain_mismatches else "PASS", "; ".join(chain_mismatches) if chain_mismatches else "all exact"),
    ]

    overall_rows = {name: summaries[name] for name in summaries}
    benchmark_selected_counts = {
        condition: Counter(
            point.selected_portfolio
            for point in points
            if point.record.draw in benchmark_draws
        )
        for condition, points in all_points.items()
        if condition != "BASELINE_ONLY"
    }
    report = render_report(
        snapshot=snapshot,
        ordered_rows=ordered_rows,
        records=records,
        benchmark=benchmark,
        summaries=overall_rows,
        block_summaries=block_summaries,
        decision_record=decision_record,
        selected_counts=benchmark_selected_counts,
        chain_checks=chain_checks,
        chain_exact=chain_exact,
        chain_mismatches=chain_mismatches,
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
        TASK_DIR / "target_features.csv",
        (
            "target_draw",
            "target_date",
            "strictly_prior_source_draw",
            "strictly_prior_source_date",
            "pre_draw_rollover_amount",
            "pre_draw_rollover_state",
            "prior_jackpot_winner_count",
            "prior_jackpot_prize",
            "prior_jackpot_last_prize",
            "prior_jackpot_per_prize",
            "target_year",
            "development_window",
        ),
        feature_rows,
    )
    (TASK_DIR / "report.md").write_text(report, encoding="utf-8")

    return {
        "snapshot": snapshot,
        "ordered_rows": ordered_rows,
        "records": records,
        "benchmark": benchmark,
        "summaries": summaries,
        "block_summaries": block_summaries,
        "decision": decision_record,
        "results_rows": results_rows,
        "placebo_rows": placebo_rows,
        "config_rows": config_rows,
    }


def render_report(
    *,
    snapshot: dict[str, Any],
    ordered_rows: tuple[RawRow, ...],
    records: tuple[TargetRecord, ...],
    benchmark: tuple[TargetRecord, ...],
    summaries: dict[str, Summary],
    block_summaries: dict[str, dict[str, Summary]],
    decision_record: dict[str, Any],
    selected_counts: dict[str, Counter[str]],
    chain_checks: int,
    chain_exact: int,
    chain_mismatches: tuple[str, ...],
) -> str:
    baseline = summaries["BASELINE_ONLY"]
    real = summaries["BASELINE_PLUS_ROLLOVER"]
    stale = summaries["STALE_PLACEBO"]
    shuffled = summaries["SHUFFLED_PLACEBO"]
    era = summaries["ERA_CONTROL"]
    target_start = benchmark[0]
    target_end = benchmark[-1]
    years = Counter(record.year for record in benchmark)
    block_lines = []
    for block_name, block_summary in block_summaries.items():
        base = block_summary["BASELINE_ONLY"]
        causal = block_summary["BASELINE_PLUS_ROLLOVER"]
        block_lines.append(
            f"| {block_name} | {base.target_count} | {fmt_rate(base.m2_plus_rate)} | "
            f"{fmt_rate(causal.m2_plus_rate)} | "
            f"{fmt_rate(causal.m2_plus_rate - base.m2_plus_rate)} |"
        )
    condition_lines = []
    for name in (
        "BASELINE_ONLY",
        "BASELINE_PLUS_ROLLOVER",
        "STATE_ONLY_SENSITIVITY",
        "STALE_PLACEBO",
        "SHUFFLED_PLACEBO",
        "ERA_CONTROL",
    ):
        current = summaries[name]
        condition_lines.append(
            f"| {name} | {current.m2_plus_hits}/{current.target_count} | "
            f"{fmt_rate(current.m2_plus_rate)} | "
            f"{current.m3_plus_hits}/{current.target_count} | "
            f"{fmt_rate(current.m3_plus_rate)} | "
            f"{current.average_matched_numbers:.4f} | "
            f"{fmt_rate(current.m2_plus_rate - baseline.m2_plus_rate)} |"
        )
    selected_lines = "\n".join(
        f"- `{condition}`: `{dict(counts)}`"
        for condition, counts in selected_counts.items()
    )
    return f"""# {TASK_ID}

TASK_ID: `{TASK_ID}`  
STATUS: **{decision_record['status']}**  
ACTION: **{decision_record['action']}**  
TARGET_COUNT: **{len(benchmark)}**  
DEVELOPMENT_WINDOWS: `DEV_W1`–`DEV_W4`, chronological; common benchmark `{target_start.draw}`–`{target_end.draw}`  
COMMON_DEVELOPMENT_BENCHMARK: **YES**  
CLEAN_HELD_OUT_CONFIRMATION: **NO**

## Question and authority

This Level-1 falsification asks whether jackpot/rollover information known
before a target draw provides repeatable incremental B649 prediction
information. The official source is the Taiwan Lottery `Lotto649Result`
endpoint already used by the repository's `TaiwanLotteryDrawProvider`:
`{SOURCE_ENDPOINT}`.

The offline raw snapshot contains `{len(ordered_rows)}` official rows,
spanning `{_iso_date(ordered_rows[0])}`–`{_iso_date(ordered_rows[-1])}`, with
reported `totalSize={snapshot['reported_total_size']}` and row digest
`{snapshot['rows_sha256']}`. The benchmark contains `{len(benchmark)}` targets
(`{target_start.draw}`–`{target_end.draw}`) across years
`{dict(sorted(years.items()))}`.

`derive_pre_draw_jackpot_rollover(...)` reads only the immediately prior row.
When that prior draw has `winnerCount=0`, the source-semantic components used
for the entering amount are `prior.lastPrize + prior.prize`; after a prior
jackpot winner the amount is left missing and the state is
`NO_ROLLOVER_RESET`, not zero-filled. A validation-only cross-row diagnostic
matched `{chain_exact}/{chain_checks}` prior no-winner transitions; the
remaining exception(s) are retained in `config_ledger.csv` and were not
repaired with target-t fields. The saved `target_features.csv` retains the
prior winner/reset state, amount, and prior jackpot pool components.

Chain diagnostic exceptions: `{'; '.join(chain_mismatches) if chain_mismatches else 'NONE'}`

## Baseline and bounded model

`BASELINE_ONLY` is the existing operational
`{BASELINE_PORTFOLIO}` producer: Horizon Minimax Disagreement, exactly two
tickets per target. The rollover model selects among the same-budget,
already-landed candidate portfolios `{', '.join(CANDIDATE_PORTFOLIOS)}` using a
small causal regime lookup trained on prior-target M2+ outcomes. The primary
key is a causal state+amount bucket (`ROLLOVER`, `ROLLOVER_LOW`,
`ROLLOVER_HIGH`, or `NO_ROLLOVER_RESET`), with a minimum of
`{MIN_REGIME_OBSERVATIONS}` earlier observations per regime. The state-only
version is a sensitivity check. This is six evaluated conditions and remains
well below the Level-1 configuration cap of 24.

Placebos use the identical candidate set, selector, metric, exposure, and
chronological fit path:

- `STALE_PLACEBO`: the state+amount pair from `{STALE_LAG_DRAWS}` eligible
  draws earlier;
- `SHUFFLED_PLACEBO`: a deterministic pair permutation preserving the exact
  feature marginal distribution;
- `ERA_CONTROL`: calendar-year regime only, testing whether a slow era label
  explains the result.

## Overall metrics

| Condition | M2+ | M2+ rate | M3+ | M3+ rate | Average matched numbers | Δ M2+ vs baseline |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(condition_lines)}

All rows use `{baseline.tickets_per_target}` tickets per target and the same
`{baseline.target_count}` targets. Selected portfolio counts are retained in
`results.csv`; the primary selector counts were:

{selected_lines}

## Chronological consistency

| Window | Targets | Baseline M2+ rate | Real rollover M2+ rate | Δ |
|---|---:|---:|---:|---:|
{chr(10).join(block_lines)}

The causal model had `{decision_record['stable_positive_blocks']}` positive and
`{decision_record['stable_nonnegative_blocks']}` non-negative development
windows. This is descriptive chronological consistency inside the shared
development benchmark, not prospective confirmation.

## Decision

- Real rollover Δ M2+: `{decision_record['real_delta_m2_plus']:.4f}`;
  meaningful threshold required at least `{decision_record['required_hit_delta']}`
  additional M2+ targets and one percentage point.
- Beats stale placebo: **{decision_record['beats_stale_placebo']}**.
- Beats shuffled placebo: **{decision_record['beats_shuffled_placebo']}**.
- Survives the calendar-year era control: **{decision_record['era_control_survives']}**.
- Chronological stability gate: **{decision_record['chronological_stability']}**.

The Level-1 decision is **{decision_record['status']}**. The prescribed action
is **{decision_record['action']}**; no additional tuning is used to rescue this
benchmark.

## Causal and filesystem checks

NO_FUTURE_LEAKAGE: **PASS** — feature derivation reads only row `t-1` or
earlier, and selector fitting uses records strictly before the current target.  
CURRENT_TARGET_POSTDRAW_FIELDS_USED: **NO** — target jackpot/sales/winner and
prize fields are never read as predictor inputs; target numbers are used only
after prediction for scoring.  
TARGET_OUTCOME_USED_AS_INPUT: **NO**.  
EQUAL_EXPOSURE: **PASS** — every condition emits/scored exactly two tickets per
target.  
PLACEBO_TESTS: **PASS** — stale, shuffled, and era-control paths completed.  
REPRODUCTION: **PASS** — the analysis is offline after the saved snapshot and
is regenerated by this script.

No database, strategy matrix, or production strategy registration was changed.

Artifacts: `report.md`, `results.csv`, `placebo_results.csv`,
`config_ledger.csv`, `target_features.csv`, `official_metadata.json`, and
`reproduce_analysis.py`.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="fetch and replace the official rich metadata snapshot before analysis",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh:
        refresh_snapshot()
    snapshot, rows = load_snapshot()
    analyze(snapshot, rows)
    print(f"wrote Level-1 artifacts under {TASK_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
