"""Minimal, standard-library-only prospective BIG_LOTTO portfolio scorer (Python 3.9).

Portfolio scoring engine for 2, 3, and 5 tickets per draw.
Computes exact multivariate hypergeometric baselines using membership masks.
Supports prospective multi-draw portfolio evaluation with fail-closed contract validation.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import zip_longest
from math import comb
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path so tools.score_biglotto_prospective_r1 is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import tools.score_biglotto_prospective_r1 as single_scorer
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import score_biglotto_prospective_r1 as single_scorer

ContractError = single_scorer.ContractError

OUTCOME_DENOMINATOR = 13983816
ALLOWED_TICKET_COUNTS = frozenset({2, 3, 5})
SINGLE_TICKET_WEIGHT_VECTOR = (6096454, 5775588, 1851150, 246820, 13545, 258, 1)
SINGLE_TICKET_EXPECTED_HITS = Fraction(36, 49)

TICKET_FIELD_CANDIDATES = ("PREDICTED_TICKETS", "PORTFOLIO_PREDICTED_NUMBERS", "TICKETS")
FORBIDDEN_SUCCESS_CLAIMS = frozenset({
    "FALSE_SUCCESS_CLAIM",
    "SUCCESS_CLAIM",
    "PREDICTIVE_SUCCESS_IMPROVEMENT",
    "IMPROVED_WIN_PROBABILITY",
    "SIGNIFICANT_LIFT",
    "PROVEN_ROI_INCREASE",
    "PROVEN_ACCURACY_IMPROVEMENT",
})
FORBIDDEN_CLAIM_VALUES = frozenset({"VERIFIED", "PROVED", "TRUE", "PASS", "ESTABLISHED"})


def _zip_strict_py39(*iterables: Any) -> Any:
    sentinel = object()
    for row in zip_longest(*iterables, fillvalue=sentinel):
        if any(value is sentinel for value in row):
            raise ValueError("zip() arguments have different lengths")
        yield row


def _validate_single_ticket(ticket: Any) -> tuple[int, ...]:
    if not isinstance(ticket, (list, tuple, set, frozenset)):
        raise ContractError("INVALID_TICKET_SIZE", "ticket must be a list/tuple")
    if len(ticket) != 6:
        raise ContractError(
            "INVALID_TICKET_SIZE",
            f"ticket requires exactly 6 numbers, got {len(ticket)}",
        )
    for n in ticket:
        if type(n) is not int:
            raise ContractError(
                "INVALID_NUMBER_TYPE",
                f"ticket numbers must be integers, got {type(n).__name__}",
            )
        if n < 1 or n > 49:
            raise ContractError(
                "OUT_OF_RANGE_NUMBER",
                f"ticket number out of range [1, 49]: {n}",
            )
    if len(set(ticket)) != 6:
        raise ContractError("DUPLICATE_NUMBERS", "ticket contains duplicate numbers")
    return tuple(sorted(ticket))


def portfolio_exact_baseline(tickets: Sequence[Sequence[int]]) -> dict[str, Any]:
    """Exact multivariate hypergeometric distribution for a portfolio of 2, 3, or 5 tickets."""
    if not isinstance(tickets, (list, tuple)):
        raise ContractError("INVALID_TICKET_COUNT", "tickets must be a list or tuple")
    m = len(tickets)
    if m not in ALLOWED_TICKET_COUNTS:
        raise ContractError("INVALID_TICKET_COUNT", f"expected 2, 3, or 5 tickets, got {m}")

    validated_tickets = [_validate_single_ticket(t) for t in tickets]

    # Build membership mask for each number in 1..49
    masks = [0] * 50
    for i, t in enumerate(validated_tickets):
        for num in t:
            masks[num] |= (1 << i)

    mask_counts = Counter(masks[1:])
    active = [(mask, count) for mask, count in mask_counts.items() if count > 0]

    max_hit_weights = [0] * 7
    total_weights = 0
    sum_hit_weights = 0
    marginal_weights = [[0] * 7 for _ in range(m)]

    def search(idx: int, remaining_draw: int, current_y: list[int]) -> None:
        nonlocal total_weights, sum_hit_weights
        if idx == len(active):
            if remaining_draw == 0:
                w = 1
                for (_, count), y in _zip_strict_py39(active, current_y):
                    w *= comb(count, y)
                total_weights += w
                ticket_hits = [0] * m
                for (mask, _), y in _zip_strict_py39(active, current_y):
                    if y > 0:
                        for i in range(m):
                            if (mask >> i) & 1:
                                ticket_hits[i] += y
                max_h = max(ticket_hits)
                max_hit_weights[max_h] += w
                sum_h = sum(ticket_hits)
                sum_hit_weights += sum_h * w
                for i in range(m):
                    marginal_weights[i][ticket_hits[i]] += w
            return

        if idx == len(active) - 1:
            count = active[idx][1]
            if remaining_draw <= count:
                current_y.append(remaining_draw)
                search(idx + 1, 0, current_y)
                current_y.pop()
            return

        for y in range(min(remaining_draw, active[idx][1]) + 1):
            current_y.append(y)
            search(idx + 1, remaining_draw - y, current_y)
            current_y.pop()

    search(0, 6, [])

    # Exact normalization & invariants check (Gate B)
    if total_weights != OUTCOME_DENOMINATOR:
        raise ContractError(
            "INCORRECT_BASELINE_NORMALIZATION",
            f"total weights {total_weights} != {OUTCOME_DENOMINATOR}",
        )
    if sum(max_hit_weights) != OUTCOME_DENOMINATOR:
        raise ContractError(
            "INCORRECT_BASELINE_NORMALIZATION",
            f"max hit weights sum {sum(max_hit_weights)} != {OUTCOME_DENOMINATOR}",
        )
    if len(max_hit_weights) != 7:
        raise ContractError(
            "INCORRECT_BASELINE_NORMALIZATION",
            "MAX_HIT_WEIGHTS length must be 7",
        )

    max_hit_probs = [Fraction(w, OUTCOME_DENOMINATOR) for w in max_hit_weights]
    if sum(max_hit_probs) != 1:
        raise ContractError(
            "INCORRECT_BASELINE_NORMALIZATION",
            "probabilities do not sum to 1",
        )

    # Marginal parity check for each ticket
    for i, marg in enumerate(marginal_weights):
        if tuple(marg) != SINGLE_TICKET_WEIGHT_VECTOR:
            raise ContractError(
                "INCORRECT_BASELINE_NORMALIZATION",
                f"ticket {i} marginal weights {marg} != {SINGLE_TICKET_WEIGHT_VECTOR}",
            )

    expected_sum_hits = Fraction(sum_hit_weights, OUTCOME_DENOMINATOR)
    if expected_sum_hits != Fraction(36 * m, 49):
        raise ContractError(
            "INCORRECT_BASELINE_NORMALIZATION",
            f"expected sum hits {expected_sum_hits} != {36 * m}/49",
        )

    expected_max_hits = sum(k * p for k, p in enumerate(max_hit_probs))

    return {
        "TICKET_COUNT": m,
        "TICKETS": [list(t) for t in validated_tickets],
        "DENOMINATOR": OUTCOME_DENOMINATOR,
        "MAX_HIT_WEIGHTS": list(max_hit_weights),
        "MAX_HIT_PROBABILITIES_0_TO_6": [float(p) for p in max_hit_probs],
        "EXACT_MAX_HIT_PROBABILITIES_0_TO_6": [str(p) for p in max_hit_probs],
        "PROBABILITIES_0_TO_6": [float(p) for p in max_hit_probs],
        "EXACT_PROBABILITIES_0_TO_6": [str(p) for p in max_hit_probs],
        "PROBABILITY_SUM": 1,
        "EXPECTED_MAX_HITS": float(expected_max_hits),
        "EXACT_EXPECTED_MAX_HITS": str(expected_max_hits),
        "MEAN_HITS": float(expected_max_hits),
        "EXPECTED_SUM_HITS": float(expected_sum_hits),
        "EXACT_EXPECTED_SUM_HITS": f"{36 * m}/49",
        "SINGLE_TICKET_MARGINAL_WEIGHTS": [list(w) for w in marginal_weights],
    }


def _extract_ticket_field(record: Mapping) -> str:
    present = [f for f in TICKET_FIELD_CANDIDATES if f in record]
    if not present:
        raise ContractError("MISSING_FIELD", "PREDICTED_TICKETS")
    if len(present) > 1:
        raise ContractError("UNEXPECTED_FIELD", f"multiple ticket fields found: {present}")
    return present[0]


def score_biglotto_portfolio_prospective(
    predictions: Sequence[Mapping],
    outcomes: Sequence[Mapping],
    *,
    experiment_id: str,
    strategy_identity: str,
    expected_draw_ids: Sequence[str],
    ticket_count: int,
) -> dict[str, Any]:
    """Validate and score prospective BIG_LOTTO portfolio predictions (Python 3.9)."""
    # 1. Gate ticket_count argument
    if type(ticket_count) is not int or ticket_count not in ALLOWED_TICKET_COUNTS:
        raise ContractError(
            "INVALID_TICKET_COUNT",
            f"ticket_count must be 2, 3, or 5; got {ticket_count}",
        )

    # 2. Containers check
    if not isinstance(predictions, (list, tuple)) or not isinstance(outcomes, (list, tuple)):
        raise ContractError("INVALID_RECORDS", "predictions and outcomes must be lists/tuples")

    if not isinstance(expected_draw_ids, (list, tuple)) or not expected_draw_ids:
        raise ContractError("INVALID_DRAW_SET", "a nonempty fixed draw set is required")

    # 3. Pre-validate predictions
    projected_predictions: list[dict[str, Any]] = []

    for item in predictions:
        if not isinstance(item, Mapping):
            raise ContractError("INVALID_RECORD", "prediction record must be a mapping")

        draw_raw = item.get("DRAW_ID")
        draw_id = str(draw_raw) if draw_raw is not None else ""
        if draw_id == single_scorer.HINDSIGHT_DRAW_ID:
            raise ContractError("HINDSIGHT_TARGET_REUSE", draw_id)

        # Check INPUT_CUTOFF explicitly for fail-closed code MISSING_INPUT_CUTOFF
        if "INPUT_CUTOFF" not in item:
            raise ContractError("MISSING_INPUT_CUTOFF", "INPUT_CUTOFF is required")
        cutoff_val = item["INPUT_CUTOFF"]
        if (
            not isinstance(cutoff_val, str)
            or not cutoff_val.strip()
            or cutoff_val != cutoff_val.strip()
        ):
            raise ContractError(
                "MISSING_INPUT_CUTOFF",
                "INPUT_CUTOFF must be nonblank, unpadded string",
            )

        ticket_field = _extract_ticket_field(item)
        raw_tickets = item[ticket_field]
        if not isinstance(raw_tickets, (list, tuple)):
            raise ContractError("INVALID_TICKET_COUNT", f"{ticket_field} must be a list/tuple")
        if len(raw_tickets) not in ALLOWED_TICKET_COUNTS:
            raise ContractError(
                "INVALID_TICKET_COUNT",
                f"ticket count {len(raw_tickets)} not in (2, 3, 5)",
            )
        if len(raw_tickets) != ticket_count:
            raise ContractError(
                "MIXED_TICKET_COUNTS",
                f"prediction tickets length {len(raw_tickets)} != "
                f"contract ticket_count {ticket_count}",
            )

        # Validate every ticket
        validated_tickets = [_validate_single_ticket(t) for t in raw_tickets]

        # Check unexpected fields and false success claims
        allowed_fields = (
            (single_scorer.PREDICTION_FIELDS - {"SIX_PREDICTED_NUMBERS"})
            | {ticket_field, "INPUT_DRAW_IDS"}
        )
        for k, v in item.items():
            if k not in allowed_fields:
                if (
                    k in FORBIDDEN_SUCCESS_CLAIMS
                    or (isinstance(v, str) and v.upper() in FORBIDDEN_CLAIM_VALUES)
                ):
                    raise ContractError(
                        "FALSE_SUCCESS_CLAIM",
                        f"false success claim in {draw_id}: {k}={v}",
                    )
                raise ContractError("UNEXPECTED_FIELD", f"unexpected field: {k}")

        # Build projected single ticket record using ticket 0
        proj = dict(item)
        del proj[ticket_field]
        proj["SIX_PREDICTED_NUMBERS"] = list(validated_tickets[0])
        projected_predictions.append(proj)

    # 4. Check for mixed ticket counts across predictions
    if predictions:
        counts = set(len(p[_extract_ticket_field(p)]) for p in predictions)
        if len(counts) > 1:
            raise ContractError(
                "MIXED_TICKET_COUNTS",
                f"predictions have mixed ticket counts: {counts}",
            )

    # 5. Delegate shared validation to single_scorer via projection
    try:
        single_result = single_scorer.score_biglotto_prospective(
            projected_predictions,
            outcomes,
            experiment_id=experiment_id,
            strategy_identity=strategy_identity,
            expected_draw_ids=expected_draw_ids,
        )
    except single_scorer.ContractError as err:
        if err.code == "MISSING_CUTOFF":
            raise ContractError("MISSING_INPUT_CUTOFF", err.args[0]) from err
        if err.code in ("TARGET_INSIDE_INPUT", "CUTOFF_NOT_BEFORE_CAPTURE"):
            raise ContractError("CUTOFF_AFTER_TARGET", err.args[0]) from err
        raise

    targets = list(single_result["FIXED_DRAW_IDS"])

    # 6. Extract official numbers
    official_map: dict[str, frozenset] = {}
    for item in outcomes:
        draw = str(item.get("DRAW_ID"))
        official_map[draw] = frozenset(item["SIX_OFFICIAL_MAIN_NUMBERS"])

    pred_map = {str(item["DRAW_ID"]): item for item in predictions}

    # 7. Multi-draw scoring per draw
    per_draw: list[dict[str, Any]] = []
    for d in targets:
        pred_item = pred_map[d]
        ticket_field = _extract_ticket_field(pred_item)
        tickets = [tuple(sorted(t)) for t in pred_item[ticket_field]]
        off_nums = official_map[d]
        ticket_hits = [len(set(t) & off_nums) for t in tickets]
        max_hits = max(ticket_hits)
        sum_hits = sum(ticket_hits)
        draw_baseline = portfolio_exact_baseline(tickets)

        per_draw.append({
            "DRAW_ID": d,
            "TICKET_HITS": ticket_hits,
            "MAX_HITS": max_hits,
            "SUM_HITS": sum_hits,
            "DRAW_EXACT_BASELINE": draw_baseline,
        })

    # 8. Cross-draw statistics
    histogram = [0] * 7
    for row in per_draw:
        histogram[row["MAX_HITS"]] += 1

    target_count = len(targets)
    observed_mean_max_hits = sum(row["MAX_HITS"] for row in per_draw) / target_count
    observed_mean_sum_hits = sum(row["SUM_HITS"] for row in per_draw) / target_count

    expected_max_hist = [
        float(sum(
            Fraction(row["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"][k], OUTCOME_DENOMINATOR)
            for row in per_draw
        ))
        for k in range(7)
    ]
    exact_expected_max_hist = [
        str(sum(
            Fraction(row["DRAW_EXACT_BASELINE"]["MAX_HIT_WEIGHTS"][k], OUTCOME_DENOMINATOR)
            for row in per_draw
        ))
        for k in range(7)
    ]
    exact_mean_exp_max = sum(
        Fraction(row["DRAW_EXACT_BASELINE"]["EXACT_EXPECTED_MAX_HITS"]) for row in per_draw
    ) / target_count
    mean_exp_max = float(exact_mean_exp_max)
    mean_exp_sum = float(Fraction(36 * ticket_count, 49))
    exact_mean_exp_sum = f"{36 * ticket_count}/49"

    portfolio_baseline = {
        "TICKET_COUNT": ticket_count,
        "TARGET_COUNT": target_count,
        "DRAW_IDS": list(targets),
        "EXPECTED_MAX_HIT_HISTOGRAM_0_TO_6": expected_max_hist,
        "EXACT_EXPECTED_MAX_HIT_HISTOGRAM_0_TO_6": exact_expected_max_hist,
        "MEAN_EXPECTED_MAX_HITS": mean_exp_max,
        "EXACT_MEAN_EXPECTED_MAX_HITS": str(exact_mean_exp_max),
        "MEAN_EXPECTED_SUM_HITS": mean_exp_sum,
        "EXACT_MEAN_EXPECTED_SUM_HITS": exact_mean_exp_sum,
        "SUCCESS_EVENT": "MAX_HITS=k, k=0..6; six main numbers only",
        "INPUT_CUTOFF_RULE": "SAME_AS_STRATEGY; cutoff < capture < draw",
    }

    return {
        "TARGET_COUNT": target_count,
        "TICKET_COUNT": ticket_count,
        "OBSERVED_MAX_HIT_HISTOGRAM_0_TO_6": histogram,
        "HIT_HISTOGRAM_0_TO_6": histogram,
        "OBSERVED_MEAN_MAX_HITS": observed_mean_max_hits,
        "MEAN_HITS": observed_mean_max_hits,
        "OBSERVED_MEAN_SUM_HITS": observed_mean_sum_hits,
        "FIXED_EXPERIMENT_ID": experiment_id,
        "EXPERIMENT_ID": experiment_id,
        "STRATEGY_IDENTITY": strategy_identity,
        "FIXED_DRAW_IDS": list(targets),
        "PER_DRAW": per_draw,
        "PORTFOLIO_BASELINE": portfolio_baseline,
        "BASELINE": portfolio_baseline,
        "EVIDENCE_STATUS": "DIAGNOSTIC_ONLY",
        "CAPTURE_TIME_INDEPENDENTLY_VERIFIED": False,
        "ORIGINAL_HISTORICAL_PARITY": "NOT_VERIFIED",
        "PREDICTIVE_SUCCESS_IMPROVEMENT": "NOT_ESTABLISHED",
        "PREDICTIVE_SUCCESS_EVIDENCE": "NOT_ESTABLISHED",
    }
