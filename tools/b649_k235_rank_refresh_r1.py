"""CLI for producing a research-only B649 K2/K3/K5 cutoff ranking artifact."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from lottolab.research.b649_k235_cutoff_rank_refresh_r1 import refresh_from_files


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute research-only B649 K2/K3/K5 rankings from existing "
            "per-draw replay evidence at an inclusive historical cutoff."
        )
    )
    parser.add_argument("--cutoff", required=True, help="Inclusive target draw cutoff")
    parser.add_argument(
        "--rank-history",
        type=Path,
        required=True,
        help="Existing rank_history.json containing the full strategy pool",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        action="append",
        required=True,
        help="Existing replay JSONL file; repeat for each source file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Research artifact output path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the selected research artifact if it already exists",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(
            f"research artifact already exists (use --overwrite explicitly): {args.output}"
        )

    artifact = refresh_from_files(
        rank_history_path=args.rank_history,
        replay_paths=args.evidence,
        cutoff_draw=args.cutoff,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "requested_cutoff": artifact["cutoff"]["requested_draw_number"],
                "actual_cutoff_applied": artifact["cutoff"]["actual_cutoff_applied"],
                "strategy_pool_count": artifact["strategy_pool"]["strategy_count"],
                "missing_strategy_count": artifact["strategy_pool"].get(
                    "missing_strategy_count", artifact["strategy_pool"]["strategy_count"]
                ),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
