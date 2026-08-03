"""Run the task-owned POWER_LOTTO Wave 1 source and replay pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lottolab.research.powerlotto_wave1 import (
    SOURCE_END_MONTH,
    SOURCE_START_MONTH,
    fetch_official_powerlotto_draws,
    load_normalized_source,
    run_replay,
)
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay selected POWER_LOTTO strategies into the task-owned Wave 1 DB."
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        required=True,
        help="Task runtime root; the SQLite DB and reports are written below this path.",
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        help="Use a task-owned normalized JSON export instead of the official API.",
    )
    parser.add_argument("--start-month", default=SOURCE_START_MONTH)
    parser.add_argument("--end-month", default=SOURCE_END_MONTH)
    parser.add_argument("--db", type=Path, help="Optional DB path inside --runtime-root.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    runtime_root: Path = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    if args.source_json is not None:
        draws, source_manifest = load_normalized_source(args.source_json.resolve())
    else:
        draws, source_manifest = fetch_official_powerlotto_draws(
            start_month=args.start_month,
            end_month=args.end_month,
        )

    source_export = runtime_root / "powerlotto_source_normalized.json"
    source_export.write_text(
        json.dumps(
            {"lottery_type": "POWER_LOTTO", "draws": [draw.canonical_dict() for draw in draws]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_manifest = {
        **source_manifest,
        "normalized_export": str(source_export),
    }
    result = run_replay(
        draws=draws,
        strategy_objects=WAVE1_STRATEGIES,
        runtime_root=runtime_root,
        db_path=args.db.resolve() if args.db is not None else None,
        source_manifest=source_manifest,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "source_sha256": result.source_sha256,
                "source_count": result.source_count,
                "selected_count": result.selected_count,
                "eligible_attempt_count": result.eligible_attempt_count,
                "complete_target_count": result.complete_target_count,
                "excluded_target_count": result.excluded_target_count,
                "failed_target_count": result.failed_target_count,
                "ticket_count": result.ticket_count,
                "db_path": str(result.db_path),
                "artifact_paths": [str(path) for path in result.artifact_paths],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
