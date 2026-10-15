"""Minimal, standard-library-only prospective BIG_LOTTO contract scorer (Python 3.9).

Call score_biglotto_prospective(predictions, outcomes, experiment_id=...,
strategy_identity=..., expected_draw_ids=...) with a separately fixed contract.
Records use the uppercase fields below; draw IDs are nine-digit strings, numbers
are integer lists/tuples, and times are timezone-aware ISO 8601 strings.
INPUT_CUTOFF is the exclusive timestamp limit of the declared input snapshot;
it must precede both capture and target draw. Optional INPUT_DRAW_IDS allows an
explicit declared snapshot inventory, checked for target contamination.

This module cannot inspect snapshot bytes, authenticate a receipt/official
source, establish when the experiment contract was fixed, or verify strategy
provenance. Even a locator or a plausible timestamp is only an assertion here.
Every accepted result is therefore DIAGNOSTIC_ONLY. No prediction generation,
network, filesystem writes, payout calculation, or significance claims occur.
"""

import re
from collections.abc import Mapping
from datetime import datetime
from fractions import Fraction
from math import comb
from typing import Any, Dict, Sequence


HINDSIGHT_DRAW_ID = "102000010"
PREDICTION_FIELDS = frozenset({
    "EXPERIMENT_ID", "DRAW_ID", "SIX_PREDICTED_NUMBERS", "STRATEGY_IDENTITY",
    "INPUT_SNAPSHOT_SHA256", "INPUT_CUTOFF", "PREDICTION_CAPTURE_ID",
    "PREDICTION_CAPTURE_TIME", "PREDRAW_EVIDENCE_LOCATOR",
})
OUTCOME_FIELDS = frozenset({
    "DRAW_ID", "SIX_OFFICIAL_MAIN_NUMBERS", "DRAW_TIME", "OFFICIAL_RESULT_SOURCE",
})


class ContractError(ValueError):
    """Fail-closed rejection with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(code + ": " + detail)


def _text(value: Any, field: str, code: str = "INVALID_FIELD") -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ContractError(code, field + " must be a nonblank, unpadded string")
    return value


def _draw_id(value: Any) -> str:
    result = _text(value, "DRAW_ID")
    if re.fullmatch(r"[0-9]{9}", result) is None:
        raise ContractError("INVALID_DRAW_ID", "expected nine ASCII digits")
    if result == HINDSIGHT_DRAW_ID:
        raise ContractError("HINDSIGHT_TARGET_REUSE", result)
    return result


def _timestamp(value: Any, field: str) -> datetime:
    raw = _text(value, field, "INVALID_TIMESTAMP")
    try:
        result = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError as exc:
        raise ContractError("INVALID_TIMESTAMP", field) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ContractError("INVALID_TIMESTAMP", field + " requires a timezone")
    return result


def _six(value: Any, field: str) -> frozenset:
    if not isinstance(value, (list, tuple)):
        raise ContractError("INVALID_NUMBERS", field + " must be a list/tuple")
    if any(isinstance(n, (list, tuple, Mapping)) for n in value) or len(value) > 6:
        raise ContractError("MULTIPLE_TICKETS_WITHOUT_CONTRACT", field)
    if len(value) != 6:
        raise ContractError("INVALID_NUMBER_COUNT", field + " requires exactly six")
    if any(type(n) is not int for n in value):
        raise ContractError("INVALID_NUMBER_TYPE", field + " requires integers")
    if any(n < 1 or n > 49 for n in value):
        raise ContractError("OUT_OF_RANGE_NUMBER", field)
    if len(set(value)) != 6:
        raise ContractError("DUPLICATE_NUMBERS", field)
    return frozenset(value)


def _record(value: Any, fields: frozenset, prediction: bool) -> Mapping:
    if not isinstance(value, Mapping):
        raise ContractError("INVALID_RECORD", "record must be a mapping")
    if prediction:
        for field, code in (
            ("INPUT_CUTOFF", "MISSING_CUTOFF"),
            ("PREDICTION_CAPTURE_ID", "MISSING_CAPTURE_ID"),
            ("PREDRAW_EVIDENCE_LOCATOR", "MISSING_PREDRAW_EVIDENCE"),
        ):
            _text(value.get(field), field, code)
    missing = fields.difference(value)
    if missing:
        raise ContractError("MISSING_FIELD", ", ".join(sorted(missing)))
    allowed = fields | ({"INPUT_DRAW_IDS"} if prediction else set())
    if set(value).difference(allowed):
        raise ContractError("UNEXPECTED_FIELD", "only documented fields are accepted")
    return value


def six_number_baseline() -> Dict[str, Any]:
    """Exact hypergeometric distribution for one fixed six-number ticket."""
    denominator = comb(49, 6)
    probabilities = [Fraction(comb(6, k) * comb(43, 6 - k), denominator) for k in range(7)]
    mean = sum((k * p for k, p in enumerate(probabilities)), Fraction(0))
    if sum(probabilities, Fraction(0)) != 1 or mean != Fraction(36, 49):
        raise ArithmeticError("invalid 6-of-49 baseline")
    return {
        "PROBABILITIES_0_TO_6": [float(p) for p in probabilities],
        "EXACT_PROBABILITIES_0_TO_6": [str(p) for p in probabilities],
        "PROBABILITY_SUM": 1,
        "MEAN_HITS": float(mean),
        "EXACT_MEAN_HITS": "36/49",
    }


def score_biglotto_prospective(
    predictions: Sequence[Mapping],
    outcomes: Sequence[Mapping],
    *,
    experiment_id: str,
    strategy_identity: str,
    expected_draw_ids: Sequence[str],
) -> Dict[str, Any]:
    """Validate the entire fixed draw set, then score; never partially accept.

    strategy_identity must name a fixed version (e.g. strategy@commit:hash).
    Equality checks this supplied identity; it does not certify the version.
    expected_draw_ids must be the full, externally prespecified evaluation set.
    Missing/extra outcomes or predictions reject the whole evaluation.
    """
    experiment_id = _text(experiment_id, "experiment_id")
    strategy_identity = _text(strategy_identity, "strategy_identity", "WRONG_STRATEGY_IDENTITY")
    if strategy_identity.upper() in {"UNKNOWN", "UNVERIFIED", "NONE"}:
        raise ContractError("WRONG_STRATEGY_IDENTITY", "a fixed strategy version is required")
    if not isinstance(expected_draw_ids, (list, tuple)) or not expected_draw_ids:
        raise ContractError("INVALID_DRAW_SET", "a nonempty fixed draw set is required")
    targets = [_draw_id(d) for d in expected_draw_ids]
    if len(set(targets)) != len(targets):
        raise ContractError("DUPLICATE_DRAW", "fixed draw set")
    if not isinstance(predictions, (list, tuple)) or not isinstance(outcomes, (list, tuple)):
        raise ContractError("INVALID_RECORDS", "predictions and outcomes must be lists/tuples")

    official = {}
    for item in outcomes:
        row = _record(item, OUTCOME_FIELDS, False)
        draw = _draw_id(row["DRAW_ID"])
        if draw in official:
            raise ContractError("DUPLICATE_DRAW", "official outcome " + draw)
        main = _six(row["SIX_OFFICIAL_MAIN_NUMBERS"], "SIX_OFFICIAL_MAIN_NUMBERS")
        when = _timestamp(row["DRAW_TIME"], "DRAW_TIME")
        _text(row["OFFICIAL_RESULT_SOURCE"], "OFFICIAL_RESULT_SOURCE")
        official[draw] = (main, when)
    if set(official) != set(targets):
        raise ContractError("DRAW_SET_MISMATCH", "official outcomes differ from fixed draw set")

    captured = {}
    capture_ids = set()
    for item in predictions:
        row = _record(item, PREDICTION_FIELDS, True)
        draw = _draw_id(row["DRAW_ID"])
        if draw in captured:
            raise ContractError("DUPLICATE_DRAW", "one prediction per experiment/draw: " + draw)
        if row["EXPERIMENT_ID"] != experiment_id:
            raise ContractError("MIXED_EXPERIMENTS", draw)
        if row["STRATEGY_IDENTITY"] != strategy_identity:
            raise ContractError("WRONG_STRATEGY_IDENTITY", draw)
        if draw not in official:
            raise ContractError("DRAW_SET_MISMATCH", "unexpected prediction " + draw)
        numbers = _six(row["SIX_PREDICTED_NUMBERS"], "SIX_PREDICTED_NUMBERS")
        digest = _text(row["INPUT_SNAPSHOT_SHA256"], "INPUT_SNAPSHOT_SHA256")
        if re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
            raise ContractError("INVALID_SNAPSHOT_SHA256", draw)
        cutoff = _timestamp(row["INPUT_CUTOFF"], "INPUT_CUTOFF")
        capture = _timestamp(row["PREDICTION_CAPTURE_TIME"], "PREDICTION_CAPTURE_TIME")
        if cutoff >= official[draw][1]:
            raise ContractError("TARGET_INSIDE_INPUT", draw)
        if capture >= official[draw][1]:
            raise ContractError("PREDICTION_AFTER_DRAW", draw)
        if cutoff >= capture:
            raise ContractError("CUTOFF_NOT_BEFORE_CAPTURE", draw)
        if "INPUT_DRAW_IDS" in row:
            inventory = row["INPUT_DRAW_IDS"]
            if not isinstance(inventory, (list, tuple)):
                raise ContractError("INVALID_INPUT_DRAW_IDS", draw)
            # Historical IDs may occur as inputs, but the target and later IDs may not.
            if any(not isinstance(d, str) or re.fullmatch(r"[0-9]{9}", d) is None
                   for d in inventory) or len(set(inventory)) != len(inventory):
                raise ContractError("INVALID_INPUT_DRAW_IDS", draw)
            if any(d >= draw for d in inventory):
                raise ContractError("TARGET_INSIDE_INPUT", draw)
        capture_id = row["PREDICTION_CAPTURE_ID"]
        if capture_id in capture_ids:
            raise ContractError("DUPLICATE_CAPTURE_ID", capture_id)
        capture_ids.add(capture_id)
        captured[draw] = numbers
    if set(captured) != set(targets):
        raise ContractError("DRAW_SET_MISMATCH", "predictions differ from fixed draw set")

    per_draw = [{"DRAW_ID": d, "HIT_COUNT": len(captured[d] & official[d][0])} for d in targets]
    histogram = [0] * 7
    for row in per_draw:
        histogram[row["HIT_COUNT"]] += 1
    baseline = six_number_baseline()
    baseline.update({
        "DRAW_IDS": list(targets),
        "TICKETS_PER_DRAW": 1,
        "SUCCESS_EVENT": "HIT_COUNT=k, k=0..6; six main numbers only",
        "INPUT_CUTOFF_RULE": "SAME_AS_STRATEGY; cutoff < capture < draw",
        "EXPECTED_HIT_HISTOGRAM_0_TO_6": [
            len(targets) * p for p in baseline["PROBABILITIES_0_TO_6"]
        ],
    })
    return {
        "TARGET_COUNT": len(targets),
        "HIT_HISTOGRAM_0_TO_6": histogram,
        "MEAN_HITS": sum(k * n for k, n in enumerate(histogram)) / len(targets),
        "FIXED_EXPERIMENT_ID": experiment_id,
        "STRATEGY_IDENTITY": strategy_identity,
        "FIXED_DRAW_IDS": list(targets),
        "TICKETS_PER_DRAW": 1,
        "PER_DRAW": per_draw,
        "EVIDENCE_STATUS": "DIAGNOSTIC_ONLY",
        "CAPTURE_TIME_INDEPENDENTLY_VERIFIED": False,
        "ORIGINAL_HISTORICAL_PARITY": "NOT_VERIFIED",
        "PREDICTIVE_SUCCESS_EVIDENCE": "NOT_ESTABLISHED",
        "BASELINE": baseline,
    }
