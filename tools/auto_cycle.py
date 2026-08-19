"""Thin shared CLI for one forward auto-cycle across supported lotteries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Protocol, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lottolab.application.forward_auto_cycle_core import (
    ForwardAutoCycleAdapter,
    ForwardAutoCycleCore,
    ForwardAutoCycleResult,
)
from lottolab.infrastructure.forward_auto_cycle_operational import ForwardCycleTarget
from tools.b649_forward_auto_cycle_adapter import B649ForwardAutoCycleAdapter
from tools.b649_operational_prediction_loop import (
    DEFAULT_OPERATION_ROOT as B649_OPERATION_ROOT,
)
from tools.b649_operational_prediction_loop import (
    PredictionTarget as B649PredictionTarget,
)
from tools.p638_forward_auto_cycle_adapter import P638ForwardAutoCycleAdapter
from tools.t539_forward_auto_cycle_adapter import T539ForwardAutoCycleAdapter


class _RenderableAdapter(Protocol):
    def target_dict(self, target: object) -> dict[str, object]: ...

    def stream_dict(self, stream: object) -> dict[str, object]: ...


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one shared forward auto-cycle.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    auto_cycle = subparsers.add_parser(
        "auto-cycle",
        help="Run target, prediction, outcome, rescore, performance, next_action.",
    )
    auto_cycle.add_argument(
        "--lottery",
        required=True,
        type=str.upper,
        choices=("B649", "T539", "P638", "ALL"),
    )
    auto_cycle.add_argument("--operation-root", type=Path)
    auto_cycle.add_argument("--database", type=Path)
    auto_cycle.add_argument("--target-draw-number")
    auto_cycle.add_argument("--target-draw-date")
    auto_cycle.add_argument("--target-scheduled-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "auto-cycle":
        raise SystemExit(f"unsupported command: {args.command}")
    lottery = cast(str, args.lottery)
    if lottery == "ALL":
        raise SystemExit("auto-cycle --lottery ALL is reserved for a future release")

    target_values = (
        cast(str | None, args.target_draw_number),
        cast(str | None, args.target_draw_date),
        cast(str | None, args.target_scheduled_at),
    )
    if any(value is not None for value in target_values) and not all(
        value is not None for value in target_values
    ):
        raise SystemExit(
            "target override requires --target-draw-number, --target-draw-date, "
            "and --target-scheduled-at together"
        )

    operation_root = cast(Path | None, args.operation_root)
    database = cast(Path | None, args.database)
    target_values_complete = all(value is not None for value in target_values)

    if lottery == "B649":
        target = (
            None
            if not target_values_complete
            else B649PredictionTarget(
                lottery_type="BIG_LOTTO",
                draw_number=cast(str, target_values[0]),
                draw_date=cast(str, target_values[1]),
                scheduled_at=cast(str, target_values[2]),
            )
        )
        adapter = B649ForwardAutoCycleAdapter(
            B649_OPERATION_ROOT if operation_root is None else operation_root,
            database=database,
            target=target,
        )
    else:
        target = (
            None
            if not target_values_complete
            else ForwardCycleTarget(
                lottery_type={"T539": "DAILY_539", "P638": "POWER_LOTTO"}[lottery],
                draw_number=cast(str, target_values[0]),
                draw_date=cast(str, target_values[1]),
                scheduled_at=cast(str, target_values[2]),
            )
        )
        adapter = (
            T539ForwardAutoCycleAdapter(
                operation_root,
                database=database,
                target=target,
            )
            if lottery == "T539"
            else P638ForwardAutoCycleAdapter(
                operation_root,
                database=database,
                target=target,
            )
        )

    cycle_adapter = cast(
        ForwardAutoCycleAdapter[
            object,
            object,
            object,
            dict[str, object],
            dict[str, object],
        ],
        adapter,
    )
    result = ForwardAutoCycleCore(cycle_adapter).run()
    print(
        json.dumps(
            _serialize_result(
                result,
                cast(_RenderableAdapter, adapter),
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _serialize_result(
    result: ForwardAutoCycleResult[
        object,
        object,
        object,
        dict[str, object],
        dict[str, object],
    ],
    adapter: _RenderableAdapter,
) -> dict[str, object]:
    target = result.target
    target_payload = None
    if target is not None:
        target_dict = adapter.target_dict
        target_payload = target_dict(target)
    stream_dict = adapter.stream_dict
    existing_streams = [stream_dict(stream) for stream in result.existing_streams]
    return {
        "lottery_type": result.lottery_type,
        "target": target_payload,
        "outcome_status": result.outcome_status,
        "next_action": result.next_action,
        "warnings": list(result.warnings),
        "existing_streams": existing_streams,
        "created_predictions": list(result.created_predictions),
        "strategy_failures": [
            {
                "error_type": failure.error_type,
                "error_message": failure.error_message,
            }
            for failure in result.strategy_failures
        ],
        "score_results": list(result.score_results),
        "score_failures": [
            {
                "error_type": failure.error_type,
                "error_message": failure.error_message,
            }
            for failure in result.score_failures
        ],
        "rescore_results": [str(value) for value in result.rescore_results],
        "current_outcome": result.current_outcome,
        "official_outcome": result.official_outcome,
        "reporting": result.reporting,
    }


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
