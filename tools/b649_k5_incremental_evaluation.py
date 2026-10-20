"""Minimal CLI for fixed, incremental B649 M0/M2 K5 records."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lottolab.research.b649_k5_incremental_evaluation import (  # noqa: E402
    RECORD_CLASSES,
    EvaluationError,
    load_official_result,
    predict_compare,
    read_jsonl,
    score_fixed_prediction,
    summarize_and_write,
)


def _base_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mode", choices=RECORD_CLASSES, required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    predict = commands.add_parser("predict", help="freeze one M0/M2 K5 comparison package")
    _base_arguments(predict)
    predict.add_argument("--history", type=Path, required=True, help="B649 JSONL snapshot")
    predict.add_argument("--target", required=True)
    predict.add_argument("--target-date", required=True)

    score = commands.add_parser("score", help="score only the stored fixed ticket package")
    _base_arguments(score)
    score.add_argument("--target", required=True)
    score.add_argument("--result-file", type=Path)

    summary = commands.add_parser("summary", help="summarize registered targets in one mode")
    _base_arguments(summary)
    return parser


def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "predict":
        package = predict_compare(
            read_jsonl(args.history),
            target_draw=args.target,
            target_date=args.target_date,
            output_root=args.output_root,
            record_class=args.mode,
        )
        return {
            "operation": "predict",
            "status": "RECORDED_OR_REUSED",
            "package": str(args.output_root / args.mode / "predictions" / f"{args.target}.json"),
            "target": package["target"],
            "methods": {
                model: {
                    "generation_status": method["generation_status"],
                    "failure_reason": method["failure_reason"],
                }
                for model, method in package["methods"].items()
            },
        }
    if args.command == "score":
        result = load_official_result(args.result_file) if args.result_file else None
        record = score_fixed_prediction(
            target_draw=args.target,
            output_root=args.output_root,
            record_class=args.mode,
            official_result=result,
        )
        return {
            "operation": "score",
            "status": record["score_status"],
            "record": str(args.output_root / args.mode / "scores" / f"{args.target}.json"),
            "target_draw": record["target_draw"],
            "methods": {
                model: {
                    "result_status": method["result_status"],
                    "successful": method["successful"],
                    "delivery_failure": method["delivery_failure"],
                }
                for model, method in record["methods"].items()
            },
        }
    if args.command == "summary":
        record = summarize_and_write(args.output_root, args.mode)
        return {
            "operation": "summary",
            "status": "WRITTEN",
            "record": str(args.output_root / args.mode / "summary.json"),
            "registered_target_n": record["registered_target_n"],
            "pending_result_n": record["pending_result_n"],
            "known_result_n": record["known_result_n"],
            "paired_known_results": record["paired_known_results"],
        }
    raise EvaluationError(f"Unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _run(args)
    except (EvaluationError, OSError, ValueError) as error:
        parser.exit(2, f"ERROR: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
