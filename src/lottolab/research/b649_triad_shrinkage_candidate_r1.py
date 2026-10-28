"""Strictly-causal B649 triad residual candidate with support-aware shrinkage.

The score measures three-number co-occurrence left after a pairwise product
approximation, corrected to match the fixed six-of-49 draw space. Rare triples
are screened by a minimum count and their standardized residuals are clipped
and shrunk with one of four frozen strengths. Portfolios are selected from the
210 six-number tickets in a top-ten residual pool.

The research replay entry point reads the local draw database through the
existing read-only replay snapshot API. It never writes to that database or
registers a strategy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, islice
from math import comb, sqrt
from pathlib import Path
from typing import Final, cast

import numpy as np
import numpy.typing as npt

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _cooccurrence,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph,
)
from lottolab.research import (
    biglotto_multi_ticket_constructors_r1 as _constructors,
)
from lottolab.research.b649_official_any_prize_exact import (
    independent_random_official_any_prize,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_fourier_chunk_k import (
    BigLottoFourierChunkK2Adapter,
    BigLottoFourierChunkK3Adapter,
    BigLottoFourierChunkK5Adapter,
)

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]

TASK_ID: Final[str] = "NUMBER2_1028_G_TRIAD_SHRINKAGE_CANDIDATE_R1"
SOURCE_HEAD: Final[str] = "cb32f260490de1635ee0c6a4e4ee275b6a10d238"
METHOD_ID: Final[str] = "B649_TRIAD_PAIRWISE_RESIDUAL_SHRINKAGE_R1"
METHOD_VERSION: Final[str] = "r1"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
PICK_COUNT: Final[int] = 6
TICKET_COUNTS: Final[tuple[int, int, int]] = (2, 3, 5)
VALIDATION_TARGET_COUNT: Final[int] = 1500
VALIDATION_WINDOWS: Final[tuple[int, int, int, int]] = (50, 300, 750, 1500)
MINIMUM_HISTORY: Final[int] = 300
FEATURE_LOOKBACK: Final[int] = 1500
TOP_NUMBER_COUNT: Final[int] = 10
MINIMUM_TRIAD_SUPPORT: Final[int] = 3
SHRINKAGE_STRENGTHS: Final[tuple[int, int, int, int]] = (2, 5, 10, 20)
MAX_ABSOLUTE_STANDARDIZED_RESIDUAL: Final[float] = 5.0
FAMILYWISE_Z_VALUE: Final[float] = 2.638
PAIRWISE_PRODUCT_BASELINE: Final[str] = (
    "N*FIXED_SIZE_CORRECTION*(P_AB*P_AC*P_BC)/(P_A*P_B*P_C)"
)
LOWER_ORDER_RESIDUAL: Final[str] = "OBSERVED_TRIAD_COUNT-PAIRWISE_PRODUCT_EXPECTED_COUNT"
SHRINKAGE_RULE: Final[str] = (
    "CLIP_Z_TO_[-5,5]*TRIAD_SUPPORT/(TRIAD_SUPPORT+FIXED_STRENGTH);"
    "ZERO_WHEN_SUPPORT_LT_3"
)
CAUSAL_CUTOFF_RULE: Final[str] = "HISTORY_PREFIX_EXCLUDES_TARGET_AND_LATER_DRAWS"
PARAMETER_SELECTION_RULE: Final[str] = (
    "SELECT_ONE_FIXED_STRENGTH_PER_K_ON_EXPLORATION_ONLY;"
    "MAX_MEAN_MAIN_HITS_PER_TICKET;TIES_PREFER_STRONGER_SHRINKAGE"
)
INCUMBENT_ID: Final[str] = "EXISTING_RESEARCH_FOURIER_CHUNK_SAME_K"
GRAPH_BASELINE_ID: Final[str] = "EXISTING_GRAPH_PAGERANK_HYBRID_DIVERSITY"
COOCCURRENCE_BASELINE_ID: Final[str] = (
    "EXISTING_CONDITIONAL_COOCCURRENCE_HYBRID_DIVERSITY"
)
FAIR_BASELINE_ID: Final[str] = "EXACT_INDEPENDENT_UNIFORM_RANDOM_SAME_K"
HYBRID_CONSTRUCTOR_ID: Final[str] = "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1"
REPLAY_METHODS: Final[tuple[str, str, str, str]] = (
    METHOD_ID,
    GRAPH_BASELINE_ID,
    COOCCURRENCE_BASELINE_ID,
    INCUMBENT_ID,
)
_BASE_SINGLE_PROBABILITY: Final[float] = PICK_COUNT / 49
_BASE_PAIR_PROBABILITY: Final[float] = 15 / comb(49, 2)
_BASE_TRIAD_PROBABILITY: Final[float] = comb(PICK_COUNT, 3) / comb(49, 3)
_PAIRWISE_FIXED_SIZE_CORRECTION: Final[float] = (
    _BASE_TRIAD_PROBABILITY
    / (_BASE_PAIR_PROBABILITY**3 / _BASE_SINGLE_PROBABILITY**3)
)
_TRIPLETS: Final[tuple[tuple[int, int, int], ...]] = tuple(
    combinations(range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1), 3)
)
_TRIAD_INDEX: Final[Mapping[tuple[int, int, int], int]] = {
    triple: index for index, triple in enumerate(_TRIPLETS)
}
_TRIAD_NUMBERS: Final[npt.NDArray[np.int64]] = np.asarray(_TRIPLETS, dtype=np.int64)
_CONSTRUCTOR = _constructors.CONSTRUCTORS[HYBRID_CONSTRUCTOR_ID]
_FOURIER_ADAPTER_TYPES = {
    2: BigLottoFourierChunkK2Adapter,
    3: BigLottoFourierChunkK3Adapter,
    5: BigLottoFourierChunkK5Adapter,
}


@dataclass(frozen=True, slots=True)
class TriadResidualState:
    """Prior-only support and standardized residual for every 3-number set."""

    history_draw_count: int
    support_counts: npt.NDArray[np.int64]
    standardized_residuals: npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class TargetPrediction:
    """One generated portfolio and its post-generation official draw scores."""

    target_index: int
    target_draw_number: str
    tickets: TicketPortfolio
    main_hits: tuple[int, ...]
    prize_tiers: tuple[str | None, ...]

    @property
    def any_prize(self) -> bool:
        return any(tier is not None for tier in self.prize_tiers)


def _validate_ticket_count(ticket_count: int) -> None:
    if type(ticket_count) is not int or ticket_count not in TICKET_COUNTS:
        raise ValueError(f"ticket_count must be one of {TICKET_COUNTS}")


def _validate_shrinkage_strength(strength: int) -> None:
    if type(strength) is not int or strength not in SHRINKAGE_STRENGTHS:
        raise ValueError(f"shrinkage_strength must be one of {SHRINKAGE_STRENGTHS}")


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values = tuple(cast(Iterable[object], raw_draw))
    except TypeError as exc:
        raise ValueError(f"history[{draw_index}] must contain exactly six integers") from exc
    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly six integers")
    if any(type(value) is not int for value in values):
        raise ValueError(f"history[{draw_index}] values must be exact integers")
    numbers = cast(tuple[int, ...], values)
    if any(number < NUMBER_DOMAIN[0] or number > NUMBER_DOMAIN[1] for number in numbers):
        raise ValueError(f"history[{draw_index}] numbers must be in 1..49")
    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six distinct numbers")
    return cast(HistoryDraw, tuple(sorted(numbers)))


def strictly_prior_history(
    history: Sequence[object] | Iterable[object],
    target_index: int,
) -> tuple[HistoryDraw, ...]:
    """Validate and return exactly the draws preceding the target index."""

    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative exact integer")
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            raw_prefix = tuple(history[:target_index])
        else:
            raw_prefix = tuple(islice(iter(history), target_index))
            if len(raw_prefix) != target_index:
                raise ValueError("target_index must not exceed history length")
    except (TypeError, IndexError) as exc:
        raise ValueError("history must be a finite chronological sequence") from exc
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise ValueError(
            f"at least {MINIMUM_HISTORY} strictly prior draws are required; "
            f"received {len(raw_prefix)}"
        )
    return tuple(_validate_draw(draw, index) for index, draw in enumerate(raw_prefix))


def _validated_prior_sequence(
    prior_history: Sequence[object] | Iterable[object],
) -> tuple[HistoryDraw, ...]:
    try:
        raw_draws = tuple(prior_history)
    except TypeError as exc:
        raise ValueError("prior_history must be a finite sequence of draws") from exc
    if len(raw_draws) < MINIMUM_HISTORY:
        raise ValueError(
            f"at least {MINIMUM_HISTORY} strictly prior draws are required; "
            f"received {len(raw_draws)}"
        )
    return tuple(_validate_draw(draw, index) for index, draw in enumerate(raw_draws))


def shrink_standardized_residual(
    residual_z: float,
    sample_support: int,
    shrinkage_strength: int,
) -> float:
    """Clip a triad residual and shrink it toward zero by its support."""

    _validate_shrinkage_strength(shrinkage_strength)
    if type(sample_support) is not int or sample_support < 0:
        raise ValueError("sample_support must be a non-negative exact integer")
    if not math.isfinite(residual_z):
        raise ValueError("residual_z must be finite")
    if sample_support < MINIMUM_TRIAD_SUPPORT:
        return 0.0
    clipped = max(
        -MAX_ABSOLUTE_STANDARDIZED_RESIDUAL,
        min(MAX_ABSOLUTE_STANDARDIZED_RESIDUAL, residual_z),
    )
    return clipped * sample_support / (sample_support + shrinkage_strength)


def compute_triad_residual_state(
    history: Sequence[object] | Iterable[object],
    target_index: int,
) -> TriadResidualState:
    """Count prior-only triples and residualize them against singles and pairs."""

    prior = strictly_prior_history(history, target_index)
    return _compute_triad_residual_state(prior)


def _compute_triad_residual_state(prior: tuple[HistoryDraw, ...]) -> TriadResidualState:
    recent = prior[-FEATURE_LOOKBACK:]
    history_count = len(recent)
    single_counts = np.zeros(50, dtype=np.int64)
    pair_counts = np.zeros((50, 50), dtype=np.int64)
    triad_counts = np.zeros(len(_TRIPLETS), dtype=np.int64)

    for draw in recent:
        for number in draw:
            single_counts[number] += 1
        for left, right in combinations(draw, 2):
            pair_counts[left, right] += 1
            pair_counts[right, left] += 1
        for triad in combinations(draw, 3):
            triad_counts[_TRIAD_INDEX[triad]] += 1

    first = _TRIAD_NUMBERS[:, 0]
    second = _TRIAD_NUMBERS[:, 1]
    third = _TRIAD_NUMBERS[:, 2]
    denominator = history_count + 1.0
    p_first = (single_counts[first] + _BASE_SINGLE_PROBABILITY) / denominator
    p_second = (single_counts[second] + _BASE_SINGLE_PROBABILITY) / denominator
    p_third = (single_counts[third] + _BASE_SINGLE_PROBABILITY) / denominator
    p_first_second = (
        pair_counts[first, second] + _BASE_PAIR_PROBABILITY
    ) / denominator
    p_first_third = (
        pair_counts[first, third] + _BASE_PAIR_PROBABILITY
    ) / denominator
    p_second_third = (
        pair_counts[second, third] + _BASE_PAIR_PROBABILITY
    ) / denominator
    expected = (
        history_count
        * _PAIRWISE_FIXED_SIZE_CORRECTION
        * p_first_second
        * p_first_third
        * p_second_third
        / (p_first * p_second * p_third)
    )
    support_as_float = triad_counts.astype(np.float64)
    residuals = (support_as_float - expected) / np.sqrt(expected + 1.0)
    residuals = np.clip(
        residuals,
        -MAX_ABSOLUTE_STANDARDIZED_RESIDUAL,
        MAX_ABSOLUTE_STANDARDIZED_RESIDUAL,
    )
    residuals[triad_counts < MINIMUM_TRIAD_SUPPORT] = 0.0
    triad_counts.setflags(write=False)
    residuals.setflags(write=False)
    return TriadResidualState(
        history_draw_count=history_count,
        support_counts=triad_counts,
        standardized_residuals=residuals,
    )


def _produce_from_state(
    state: TriadResidualState,
    ticket_count: int,
    shrinkage_strength: int,
) -> TicketPortfolio:
    _validate_ticket_count(ticket_count)
    _validate_shrinkage_strength(shrinkage_strength)
    support = state.support_counts.astype(np.float64)
    weights = state.standardized_residuals * support / (support + shrinkage_strength)
    weights[state.support_counts < MINIMUM_TRIAD_SUPPORT] = 0.0
    number_weights = np.bincount(
        _TRIAD_NUMBERS.reshape(-1),
        weights=np.repeat(weights, 3),
        minlength=50,
    )
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-float(number_weights[number]), number),
        )[:TOP_NUMBER_COUNT]
    )
    source_tickets = tuple(
        cast(
            Ticket,
            tuple(sorted(ordered_numbers[position] for position in rank_positions)),
        )
        for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT)
    )
    ticket_triads = tuple(
        tuple(_TRIAD_INDEX[triad] for triad in combinations(ticket, 3))
        for ticket in source_tickets
    )
    ordered_indices = sorted(
        range(len(source_tickets)),
        key=lambda index: (
            -round(float(weights[list(ticket_triads[index])].sum()), 12),
            source_tickets[index],
        ),
    )
    ranked_tickets = tuple(source_tickets[index] for index in ordered_indices)
    five_ticket_portfolio = _CONSTRUCTOR(ranked_tickets, 5)
    portfolio = cast(TicketPortfolio, five_ticket_portfolio[:ticket_count])
    if len(portfolio) != ticket_count or len(set(portfolio)) != ticket_count:
        raise RuntimeError("candidate constructor did not produce requested unique tickets")
    return portfolio


def produce_b649_triad_shrinkage_candidate_r1(
    history: Sequence[object] | Iterable[object],
    target_index: int,
    ticket_count: int,
    shrinkage_strength: int,
) -> TicketPortfolio:
    """Produce K2/K3/K5 using only the strictly earlier draw prefix."""

    _validate_ticket_count(ticket_count)
    _validate_shrinkage_strength(shrinkage_strength)
    prior = strictly_prior_history(history, target_index)
    return _produce_from_state(
        _compute_triad_residual_state(prior),
        ticket_count,
        shrinkage_strength,
    )


def _validate_replay_draws(draws: Sequence[ReplayDraw]) -> tuple[ReplayDraw, ...]:
    frozen = tuple(draws)
    if not frozen:
        raise ValueError("historical replay requires at least one BIG_LOTTO draw")
    previous_key: tuple[object, int] | None = None
    seen_draw_numbers: set[str] = set()
    for index, draw in enumerate(frozen):
        if type(draw) is not ReplayDraw or draw.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError(f"draws[{index}] must be a BIG_LOTTO ReplayDraw")
        canonical_main = _validate_draw(draw.main_numbers, index)
        if draw.main_numbers != canonical_main:
            raise ValueError(f"draws[{index}] main_numbers must be ascending")
        if (
            draw.special_number is None
            or not 1 <= draw.special_number <= 49
            or draw.special_number in canonical_main
        ):
            raise ValueError(
                f"draws[{index}] must have one legal non-overlapping special number"
            )
        if draw.draw_number in seen_draw_numbers:
            raise ValueError(f"draws[{index}] duplicates draw number {draw.draw_number}")
        if previous_key is not None and draw.sort_key <= previous_key:
            raise ValueError("historical replay draws must be in strict chronological order")
        previous_key = draw.sort_key
        seen_draw_numbers.add(draw.draw_number)
    return frozen


def _evaluate_portfolio(
    tickets: TicketPortfolio,
    target: ReplayDraw,
    target_index: int,
) -> TargetPrediction:
    _validate_ticket_count(len(tickets))
    hits: list[int] = []
    tiers: list[str | None] = []
    for ticket in tickets:
        result = evaluate_lottery_prize(
            lottery_type=LotteryType.BIG_LOTTO,
            predicted_main_numbers=ticket,
            predicted_special_number=None,
            winning_main_numbers=target.main_numbers,
            winning_special_number=target.special_number,
        )
        hits.append(result.zone1_hits)
        tiers.append(result.prize_tier)
    return TargetPrediction(
        target_index=target_index,
        target_draw_number=target.draw_number,
        tickets=tickets,
        main_hits=tuple(hits),
        prize_tiers=tuple(tiers),
    )


def _causal_rows(prior_draws: Sequence[ReplayDraw]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=draw.draw_number,
            date=draw.draw_date.isoformat(),
            numbers=draw.main_numbers,
        )
        for draw in prior_draws
    )


def _prediction_payload(prediction: TargetPrediction) -> dict[str, object]:
    return {
        "draw_number": prediction.target_draw_number,
        "tickets": [list(ticket) for ticket in prediction.tickets],
    }


def _prediction_sha256(predictions: Sequence[TargetPrediction]) -> str:
    payload = [_prediction_payload(prediction) for prediction in predictions]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _summarize_predictions(
    predictions: Sequence[TargetPrediction],
    ticket_count: int,
    *,
    expected_target_count: int,
) -> dict[str, object]:
    draw_count = len(predictions)
    if draw_count == 0:
        return {
            "status": "UNAVAILABLE",
            "requested_target_count": expected_target_count,
            "available_target_count": 0,
        }
    tier_counts: dict[str, int] = {}
    for prediction in predictions:
        for tier in prediction.prize_tiers:
            label = "NO_PRIZE" if tier is None else tier
            tier_counts[label] = tier_counts.get(label, 0) + 1
    ticket_total = draw_count * ticket_count
    main_hit_total = sum(sum(prediction.main_hits) for prediction in predictions)
    return {
        "status": "AVAILABLE" if draw_count == expected_target_count else "PARTIAL",
        "requested_target_count": expected_target_count,
        "available_target_count": draw_count,
        "first_target_draw": predictions[0].target_draw_number,
        "last_target_draw": predictions[-1].target_draw_number,
        "any_prize_draw_count": sum(prediction.any_prize for prediction in predictions),
        "any_prize_rate": sum(prediction.any_prize for prediction in predictions) / draw_count,
        "m3_plus_draw_rate": sum(
            any(hit >= 3 for hit in prediction.main_hits) for prediction in predictions
        )
        / draw_count,
        "main_hits_per_ticket": main_hit_total / ticket_total,
        "main_hits_per_draw": main_hit_total / draw_count,
        "mean_best_main_hits_per_draw": sum(
            max(prediction.main_hits) for prediction in predictions
        )
        / draw_count,
        "prize_tier_ticket_counts": dict(sorted(tier_counts.items())),
        "prediction_sha256": _prediction_sha256(predictions),
    }


def _wilson_lower_bound(successes: int, sample_count: int, z_value: float) -> float:
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    rate = successes / sample_count
    z_squared = z_value * z_value
    denominator = 1 + z_squared / sample_count
    center = rate + z_squared / (2 * sample_count)
    radius = sqrt(
        rate * (1 - rate) / sample_count + z_squared / (4 * sample_count * sample_count)
    )
    return (center - radius) / denominator


def _paired_win_rate_comparison(
    candidate: Sequence[TargetPrediction],
    baseline: Sequence[TargetPrediction],
    *,
    z_value: float,
) -> dict[str, object]:
    baseline_by_index = {prediction.target_index: prediction for prediction in baseline}
    common = [
        (prediction, baseline_by_index[prediction.target_index])
        for prediction in candidate
        if prediction.target_index in baseline_by_index
    ]
    if not common:
        return {"status": "UNAVAILABLE", "common_target_count": 0}
    differences = [
        int(candidate_prediction.any_prize) - int(baseline_prediction.any_prize)
        for candidate_prediction, baseline_prediction in common
    ]
    mean_difference = sum(differences) / len(differences)
    if len(differences) > 1:
        variance = sum((value - mean_difference) ** 2 for value in differences) / (
            len(differences) - 1
        )
        standard_error = sqrt(variance / len(differences))
    else:
        standard_error = 0.0
    candidate_win_rate = sum(
        prediction.any_prize for prediction, _baseline in common
    ) / len(common)
    baseline_win_rate = sum(
        prediction.any_prize for _candidate, prediction in common
    ) / len(common)
    return {
        "status": "AVAILABLE",
        "common_target_count": len(common),
        "candidate_any_prize_rate": candidate_win_rate,
        "baseline_any_prize_rate": baseline_win_rate,
        "paired_any_prize_rate_delta": mean_difference,
        "paired_any_prize_rate_delta_pp": mean_difference * 100,
        "paired_ci": [
            mean_difference - z_value * standard_error,
            mean_difference + z_value * standard_error,
        ],
    }


def _fair_baseline_summary(ticket_count: int, target_count: int) -> dict[str, object]:
    exact_probability = independent_random_official_any_prize(ticket_count)
    return {
        "status": "EXACT_EXPECTATION",
        "requested_target_count": target_count,
        "available_target_count": target_count,
        "tickets_per_target": ticket_count,
        "random_ticket_protocol": "INDEPENDENT_UNIFORM_LEGAL_TICKETS_WITH_REPLACEMENT",
        "expected_any_prize_rate": float(exact_probability),
        "expected_any_prize_rate_exact": (
            f"{exact_probability.numerator}/{exact_probability.denominator}"
        ),
        "expected_main_hits_per_ticket": 36 / 49,
    }


def _history_fingerprint(draws: Sequence[ReplayDraw]) -> str:
    payload = [
        {
            "draw_number": draw.draw_number,
            "draw_date": draw.draw_date.isoformat(),
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in draws
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validation_phase_metrics(
    draws: tuple[ReplayDraw, ...],
    validation_indices: tuple[int, ...],
    prediction_books: Mapping[tuple[str, int], Mapping[int, TargetPrediction]],
    *,
    comparison_z: float,
) -> dict[str, object]:
    windows: dict[str, object] = {}
    for window in VALIDATION_WINDOWS:
        indices = validation_indices[-window:]
        targets: dict[str, object] = {}
        for ticket_count in TICKET_COUNTS:
            method_metrics: dict[str, object] = {}
            method_predictions: dict[str, tuple[TargetPrediction, ...]] = {}
            for method in REPLAY_METHODS:
                book = prediction_books[(method, ticket_count)]
                predictions = tuple(book[index] for index in indices if index in book)
                method_predictions[method] = predictions
                method_metrics[method] = _summarize_predictions(
                    predictions,
                    ticket_count,
                    expected_target_count=window,
                )
            fair = _fair_baseline_summary(ticket_count, window)
            method_metrics[FAIR_BASELINE_ID] = fair
            comparisons: dict[str, object] = {}
            candidate = method_predictions[METHOD_ID]
            for baseline in (GRAPH_BASELINE_ID, COOCCURRENCE_BASELINE_ID, INCUMBENT_ID):
                comparisons[baseline] = _paired_win_rate_comparison(
                    candidate,
                    method_predictions[baseline],
                    z_value=comparison_z,
                )
            candidate_wins = sum(prediction.any_prize for prediction in candidate)
            fair_probability = cast(float, fair["expected_any_prize_rate"])
            fair_lower = _wilson_lower_bound(
                candidate_wins,
                len(candidate),
                1.96,
            )
            comparisons[FAIR_BASELINE_ID] = {
                "status": "AVAILABLE" if candidate else "UNAVAILABLE",
                "candidate_any_prize_rate": (
                    candidate_wins / len(candidate) if candidate else None
                ),
                "fair_expected_any_prize_rate": fair_probability,
                "candidate_wilson_95_lower_bound": fair_lower if candidate else None,
                "delta_vs_fair_expected_rate": (
                    candidate_wins / len(candidate) - fair_probability if candidate else None
                ),
            }
            targets[str(ticket_count)] = {
                "method_metrics": method_metrics,
                "candidate_vs_baseline": comparisons,
            }
        windows[str(window)] = {
            "requested_target_count": window,
            "first_target_draw": draws[indices[0]].draw_number,
            "last_target_draw": draws[indices[-1]].draw_number,
            "ticket_counts": targets,
        }
    return windows


def _assess_validation_gain(
    validation_metrics: Mapping[str, object],
    *,
    familywise_z: float,
) -> dict[str, object]:
    full_window = cast(
        Mapping[str, object],
        validation_metrics[str(VALIDATION_TARGET_COUNT)],
    )
    per_ticket_count = cast(Mapping[str, object], full_window["ticket_counts"])
    decisions: dict[str, object] = {}
    credible_ticket_counts: list[int] = []
    for ticket_count in TICKET_COUNTS:
        cell = cast(Mapping[str, object], per_ticket_count[str(ticket_count)])
        comparisons = cast(Mapping[str, object], cell["candidate_vs_baseline"])
        baseline_checks: dict[str, bool] = {}
        for baseline in (GRAPH_BASELINE_ID, COOCCURRENCE_BASELINE_ID, INCUMBENT_ID):
            comparison = cast(Mapping[str, object], comparisons[baseline])
            interval = comparison.get("paired_ci")
            baseline_checks[baseline] = bool(
                isinstance(interval, list)
                and len(interval) == 2
                and cast(float, interval[0]) > 0
            )
        fair_comparison = cast(Mapping[str, object], comparisons[FAIR_BASELINE_ID])
        candidate_rate = cast(float, fair_comparison["candidate_any_prize_rate"])
        candidate_metrics = cast(
            Mapping[str, object],
            cast(Mapping[str, object], cell["method_metrics"])[METHOD_ID],
        )
        wins = cast(int, candidate_metrics["any_prize_draw_count"])
        sample_count = cast(int, candidate_metrics["available_target_count"])
        fair_lower = _wilson_lower_bound(wins, sample_count, familywise_z)
        fair_expected = cast(float, fair_comparison["fair_expected_any_prize_rate"])
        fair_check = fair_lower > fair_expected
        credible = bool(all((*baseline_checks.values(), fair_check)))
        if credible:
            credible_ticket_counts.append(ticket_count)
        decisions[str(ticket_count)] = {
            "credible_gain": credible,
            "paired_lower_ci_above_zero_by_baseline": baseline_checks,
            "candidate_wilson_lower_bound": fair_lower,
            "fair_expected_any_prize_rate": fair_expected,
            "candidate_any_prize_rate": candidate_rate,
            "candidate_lower_bound_above_fair_expectation": fair_check,
        }
    return {
        "status": "CREDIBLE_GAIN" if credible_ticket_counts else "NO_GAIN",
        "primary_metric": "OFFICIAL_ANY_PRIZE_RATE",
        "validation_window_target_count": VALIDATION_TARGET_COUNT,
        "familywise_z_value": familywise_z,
        "familywise_control": "BONFERRONI_APPROXIMATION_OVER_K_AND_FOUR_BASELINES",
        "credible_ticket_counts": credible_ticket_counts,
        "by_ticket_count": decisions,
    }


def run_historical_backtest(
    source_draws: Sequence[ReplayDraw],
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    """Select shrinkage on exploration, then replay the frozen choice on holdout."""

    draws = _validate_replay_draws(source_draws)
    if len(draws) < MINIMUM_HISTORY + VALIDATION_TARGET_COUNT:
        raise ValueError(
            f"need at least {MINIMUM_HISTORY + VALIDATION_TARGET_COUNT} draws "
            "to preserve a 1,500-target validation segment"
        )
    validation_start = len(draws) - VALIDATION_TARGET_COUNT
    if validation_start <= MINIMUM_HISTORY:
        raise ValueError("exploration segment must include at least one eligible target")
    main_history = tuple(draw.main_numbers for draw in draws)
    exploration_indices = tuple(range(MINIMUM_HISTORY, validation_start))
    validation_indices = tuple(range(validation_start, len(draws)))

    exploration_candidate: dict[tuple[int, int], list[TargetPrediction]] = {
        (ticket_count, strength): []
        for ticket_count in TICKET_COUNTS
        for strength in SHRINKAGE_STRENGTHS
    }
    exploration_incumbent: dict[int, list[TargetPrediction]] = {
        ticket_count: [] for ticket_count in TICKET_COUNTS
    }
    incumbent_types = {
        ticket_count: adapter_type()
        for ticket_count, adapter_type in _FOURIER_ADAPTER_TYPES.items()
    }

    for target_index in exploration_indices:
        prior = _validated_prior_sequence(main_history[:target_index])
        state = _compute_triad_residual_state(prior)
        target = draws[target_index]
        portfolios_by_strength = {
            strength: _produce_from_state(state, 5, strength)
            for strength in SHRINKAGE_STRENGTHS
        }
        for strength, portfolio in portfolios_by_strength.items():
            for ticket_count in TICKET_COUNTS:
                prediction = _evaluate_portfolio(
                    cast(TicketPortfolio, portfolio[:ticket_count]),
                    target,
                    target_index,
                )
                exploration_candidate[(ticket_count, strength)].append(prediction)
        if target_index >= incumbent_types[2].min_history:
            rows = _causal_rows(draws[:target_index])
            for ticket_count, adapter in incumbent_types.items():
                tickets = cast(
                    TicketPortfolio,
                    adapter.get_bets(rows, LotteryType.BIG_LOTTO),
                )
                exploration_incumbent[ticket_count].append(
                    _evaluate_portfolio(tickets, target, target_index)
                )

    selected_strengths: dict[int, int] = {}
    exploration_strength_metrics: dict[str, object] = {}
    for ticket_count in TICKET_COUNTS:
        per_strength: dict[str, object] = {}
        for strength in SHRINKAGE_STRENGTHS:
            predictions = exploration_candidate[(ticket_count, strength)]
            per_strength[str(strength)] = _summarize_predictions(
                predictions,
                ticket_count,
                expected_target_count=len(exploration_indices),
            )
        selected_strength = max(
            SHRINKAGE_STRENGTHS,
            key=lambda strength: (
                cast(
                    float,
                    cast(Mapping[str, object], per_strength[str(strength)])[
                        "main_hits_per_ticket"
                    ],
                ),
                strength,
            ),
        )
        selected_strengths[ticket_count] = selected_strength
        incumbent_predictions = exploration_incumbent[ticket_count]
        exploration_strength_metrics[str(ticket_count)] = {
            "selected_shrinkage_strength": selected_strength,
            "selection_rule": PARAMETER_SELECTION_RULE,
            "candidate_by_strength": per_strength,
            "same_k_incumbent": _summarize_predictions(
                incumbent_predictions,
                ticket_count,
                expected_target_count=len(incumbent_predictions),
            ),
            "same_k_incumbent_available_target_count": len(incumbent_predictions),
            "graph_baseline_status": "NOT_AVAILABLE_IN_EXPLORATION_SEGMENT",
            "conditional_cooccurrence_baseline_status": (
                "NOT_AVAILABLE_IN_EXPLORATION_SEGMENT"
            ),
        }

    prediction_books: dict[tuple[str, int], dict[int, TargetPrediction]] = {
        (method, ticket_count): {}
        for method in REPLAY_METHODS
        for ticket_count in TICKET_COUNTS
    }
    for completed, target_index in enumerate(validation_indices, start=1):
        prior = _validated_prior_sequence(main_history[:target_index])
        state = _compute_triad_residual_state(prior)
        target = draws[target_index]
        portfolios_by_strength = {
            strength: _produce_from_state(state, 5, strength)
            for strength in set(selected_strengths.values())
        }
        for ticket_count, strength in selected_strengths.items():
            prediction = _evaluate_portfolio(
                cast(TicketPortfolio, portfolios_by_strength[strength][:ticket_count]),
                target,
                target_index,
            )
            prediction_books[(METHOD_ID, ticket_count)][target_index] = prediction

        if target_index >= _graph.MINIMUM_HISTORY:
            graph_source = _graph.produce_source_ticket_universe(main_history, target_index)
            graph_k5 = _constructors.CONSTRUCTORS[HYBRID_CONSTRUCTOR_ID](graph_source, 5)
            for ticket_count in TICKET_COUNTS:
                prediction_books[(GRAPH_BASELINE_ID, ticket_count)][target_index] = (
                    _evaluate_portfolio(
                        cast(TicketPortfolio, graph_k5[:ticket_count]),
                        target,
                        target_index,
                    )
                )
        if target_index >= _cooccurrence.MINIMUM_HISTORY:
            cooccurrence_source = _cooccurrence.produce_source_ticket_universe(
                main_history,
                target_index,
            )
            cooccurrence_k5 = _constructors.CONSTRUCTORS[HYBRID_CONSTRUCTOR_ID](
                cooccurrence_source,
                5,
            )
            for ticket_count in TICKET_COUNTS:
                prediction_books[(COOCCURRENCE_BASELINE_ID, ticket_count)][
                    target_index
                ] = _evaluate_portfolio(
                    cast(TicketPortfolio, cooccurrence_k5[:ticket_count]),
                    target,
                    target_index,
                )

        rows = _causal_rows(draws[:target_index])
        for ticket_count, adapter in incumbent_types.items():
            tickets = cast(
                TicketPortfolio,
                adapter.get_bets(rows, LotteryType.BIG_LOTTO),
            )
            prediction_books[(INCUMBENT_ID, ticket_count)][target_index] = (
                _evaluate_portfolio(tickets, target, target_index)
            )
        if progress is not None and (completed % 50 == 0 or completed == len(validation_indices)):
            progress(completed, len(validation_indices))

    validation_metrics = _validation_phase_metrics(
        draws,
        validation_indices,
        prediction_books,
        comparison_z=FAMILYWISE_Z_VALUE,
    )
    gain_decision = _assess_validation_gain(
        validation_metrics,
        familywise_z=FAMILYWISE_Z_VALUE,
    )
    exploration_start = draws[exploration_indices[0]]
    exploration_end = draws[exploration_indices[-1]]
    validation_start_draw = draws[validation_indices[0]]
    validation_end_draw = draws[validation_indices[-1]]
    return {
        "task_id": TASK_ID,
        "source_head": SOURCE_HEAD,
        "method": {
            "method_id": METHOD_ID,
            "version": METHOD_VERSION,
            "feature": "STRICTLY_PRIOR_THREE_NUMBER_SAME_DRAW_COUNTS",
            "pairwise_explanation": PAIRWISE_PRODUCT_BASELINE,
            "residual": LOWER_ORDER_RESIDUAL,
            "fixed_size_draw_correction": _PAIRWISE_FIXED_SIZE_CORRECTION,
            "minimum_history": MINIMUM_HISTORY,
            "feature_lookback_cap": FEATURE_LOOKBACK,
            "minimum_triad_support": MINIMUM_TRIAD_SUPPORT,
            "maximum_absolute_standardized_residual": (
                MAX_ABSOLUTE_STANDARDIZED_RESIDUAL
            ),
            "shrinkage_strength_candidates": list(SHRINKAGE_STRENGTHS),
            "shrinkage_rule": SHRINKAGE_RULE,
            "ticket_counts": list(TICKET_COUNTS),
            "top_number_count": TOP_NUMBER_COUNT,
            "causal_cutoff_rule": CAUSAL_CUTOFF_RULE,
        },
        "source": {
            "draw_count": len(draws),
            "first_draw_number": draws[0].draw_number,
            "first_draw_date": draws[0].draw_date.isoformat(),
            "last_draw_number": draws[-1].draw_number,
            "last_draw_date": draws[-1].draw_date.isoformat(),
            "history_sha256": _history_fingerprint(draws),
            "database_access": "EXISTING_READ_ONLY_REPLAY_SNAPSHOT_API",
        },
        "exploration": {
            "target_count": len(exploration_indices),
            "first_target_index": exploration_indices[0],
            "last_target_index": exploration_indices[-1],
            "first_target_draw": exploration_start.draw_number,
            "last_target_draw": exploration_end.draw_number,
            "used_for": "SHRINKAGE_STRENGTH_SELECTION_ONLY",
            "selected_strength_by_ticket_count": {
                str(ticket_count): strength
                for ticket_count, strength in selected_strengths.items()
            },
            "metrics_by_ticket_count": exploration_strength_metrics,
        },
        "validation": {
            "target_count": len(validation_indices),
            "first_target_index": validation_indices[0],
            "last_target_index": validation_indices[-1],
            "first_target_draw": validation_start_draw.draw_number,
            "last_target_draw": validation_end_draw.draw_number,
            "parameters_frozen_before_validation": True,
            "windows": list(VALIDATION_WINDOWS),
            "metrics": validation_metrics,
            "gain_decision": gain_decision,
        },
        "baselines": {
            "graph": {
                "baseline_id": GRAPH_BASELINE_ID,
                "source_module": _graph.__name__,
                "ticket_constructor": HYBRID_CONSTRUCTOR_ID,
                "minimum_prior_history": _graph.MINIMUM_HISTORY,
            },
            "conditional_cooccurrence": {
                "baseline_id": COOCCURRENCE_BASELINE_ID,
                "source_module": _cooccurrence.__name__,
                "ticket_constructor": HYBRID_CONSTRUCTOR_ID,
                "minimum_prior_history": _cooccurrence.MINIMUM_HISTORY,
            },
            "same_k_incumbent": {
                "baseline_id": INCUMBENT_ID,
                "strategy_ids": {
                    str(ticket_count): adapter.strategy_id
                    for ticket_count, adapter in incumbent_types.items()
                },
                "minimum_prior_history": 500,
            },
            "fair": {
                "baseline_id": FAIR_BASELINE_ID,
                "definition": (
                    "EXACT_INDEPENDENT_RANDOM_PORTFOLIO_PROBABILITY_UNDER_UNIFORM_FAIR_DRAWS"
                ),
                "source_module": "lottolab.research.b649_official_any_prize_exact",
            },
        },
        "result_classification": {
            "exploration": "COMPLETED",
            "validation": "COMPLETED",
            "unverified": [
                "PROSPECTIVE_FUTURE_DRAW_PERFORMANCE",
                "INDEPENDENT_EXTERNAL_REPLICATION",
                "PRODUCTION_REGISTRY_OR_LIVE_INTEGRATION",
            ],
            "gain_status": gain_decision["status"],
        },
    }


def run_read_only_historical_backtest(
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    """Load official history through the existing read-only replay snapshot."""

    from lottolab.interfaces.cli.historical_replay_biglotto import (
        build_b649_replay_source_snapshot,
    )

    source = build_b649_replay_source_snapshot()
    return run_historical_backtest(source.historical_draws, progress=progress)


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Task-owned result.json path inside .task-data/" + TASK_ID,
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    allowed_output = project_root / ".task-data" / TASK_ID / "result.json"
    output_path = args.output.resolve(strict=False)
    if output_path != allowed_output:
        parser.error(f"--output must equal the task result path: {allowed_output}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def report_progress(completed: int, total: int) -> None:
        print(f"validation_progress={completed}/{total}", flush=True)

    report = run_read_only_historical_backtest(progress=report_progress)
    output_path.write_text(_canonical_json(report) + chr(10), encoding="utf-8")
    summary = {
        "output": str(output_path),
        "draw_count": report["source"]["draw_count"],
        "validation_target_count": report["validation"]["target_count"],
        "gain_status": report["validation"]["gain_decision"]["status"],
        "result_classification": report["result_classification"],
    }
    print(_canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
