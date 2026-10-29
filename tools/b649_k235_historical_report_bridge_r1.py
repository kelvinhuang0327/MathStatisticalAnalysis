"""Compose a historical K235 report from saved C ranking and per-target JSONL files."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from lottolab.research.b649_k235_historical_report_bridge_r1 import build_historical_report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rank-history", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--saved-ranking", type=Path)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--evidence-kind", choices=("OBSERVED", "SYNTHETIC"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"report already exists: {args.output}")
    report = build_historical_report(
        rank_history_path=args.rank_history,
        replay_paths=args.evidence,
        cutoff_draw=args.cutoff,
        evidence_kind=args.evidence_kind,
        saved_ranking_path=args.saved_ranking,
    )
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "evidence_kind": report["evidence_kind"],
                "output": str(args.output.resolve()),
                "validation": report.get("validation"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
