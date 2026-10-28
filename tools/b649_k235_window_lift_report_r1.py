#!/usr/bin/env python3
"""Evaluate a supplied JSON BIG_LOTTO history without opening any data store.

Input uses ``B649_K235_WINDOW_LIFT_INPUT_R1`` with ``draws`` rows containing
``draw_id``, ISO ``draw_date``, six ``winning_main_numbers``, and one
``winning_special_number``. ``predictions`` rows contain ``strategy_id``,
``draw_id``, ``status`` (``OK``, ``FAILED``, or ``NOT_EVALUABLE``), and the
ordered ``native_tickets`` array. K values use the first 2, 3, or 5 tickets in
that native order. An optional ``incumbent_strategy_id`` enables paired
comparisons. Recent windows are selected over target draws; only evaluable
predictions enter each denominator.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k235_window_lift_report_r1 import (
    HistoricalDrawOutcome,
    K235WindowLiftError,
    PredictionStatus,
    StrategyTargetReplay,
    evaluate_k235_history,
)

INPUT_SCHEMA_VERSION = "B649_K235_WINDOW_LIFT_INPUT_R1"


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise K235WindowLiftError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _build_report(document: object) -> dict[str, object]:
    source = _require_mapping(document, "input")
    if source.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise K235WindowLiftError(f"schema_version must equal {INPUT_SCHEMA_VERSION}")
    raw_draws = source.get("draws")
    raw_predictions = source.get("predictions")
    if not isinstance(raw_draws, list) or not isinstance(raw_predictions, list):
        raise K235WindowLiftError("draws and predictions must be JSON arrays")

    outcomes: list[HistoricalDrawOutcome] = []
    for index, raw_draw in enumerate(cast(list[object], raw_draws)):
        row = _require_mapping(raw_draw, f"draws[{index}]")
        try:
            outcomes.append(
                HistoricalDrawOutcome(
                    draw_id=row["draw_id"],
                    draw_date=date.fromisoformat(row["draw_date"]),
                    winning_main_numbers=tuple(row["winning_main_numbers"]),
                    winning_special_number=row["winning_special_number"],
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise K235WindowLiftError(f"invalid draws[{index}]: {exc}") from exc

    predictions: list[StrategyTargetReplay] = []
    for index, raw_prediction in enumerate(cast(list[object], raw_predictions)):
        row = _require_mapping(raw_prediction, f"predictions[{index}]")
        raw_tickets = row.get("native_tickets")
        if raw_tickets is not None and not isinstance(raw_tickets, list):
            raise K235WindowLiftError(
                f"predictions[{index}].native_tickets must be an array or null"
            )
        tickets = (
            tuple(
                tuple(cast(list[int], ticket)) if isinstance(ticket, list) else ticket
                for ticket in cast(list[Any], raw_tickets)
            )
            if raw_tickets is not None
            else None
        )
        try:
            predictions.append(
                StrategyTargetReplay(
                    strategy_id=row["strategy_id"],
                    draw_id=row["draw_id"],
                    native_tickets=tickets,
                    status=PredictionStatus(row.get("status", "OK")),
                    failure_reason=row.get("failure_reason"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise K235WindowLiftError(f"invalid predictions[{index}]: {exc}") from exc

    incumbent = source.get("incumbent_strategy_id")
    if incumbent is not None and not isinstance(incumbent, str):
        raise K235WindowLiftError("incumbent_strategy_id must be text or null")
    return evaluate_k235_history(
        outcomes,
        predictions,
        incumbent_strategy_id=incumbent,
    ).to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="input JSON using the R1 schema")
    parser.add_argument(
        "--output",
        default="-",
        help="output JSON path, or '-' for stdout (default: '-')",
    )
    args = parser.parse_args(argv)
    try:
        document = json.loads(Path(args.input).read_text(encoding="utf-8"))
        report = _build_report(document)
        # Normalize JSON keys and tuples before emitting the canonical document.
        normalized = json.loads(
            json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True)
        )
        output = json.dumps(normalized, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        if args.output == "-":
            sys.stdout.write(output)
        else:
            Path(args.output).write_text(output, encoding="utf-8")
    except (OSError, json.JSONDecodeError, K235WindowLiftError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
