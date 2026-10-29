"""Create the incremental K2/K3/K5 ranking artifacts through draw 115000099."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lottolab.research.b649_k235_incremental_rank_099_r1 import (
    build_from_fixed_paths,
)

EVIDENCE_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/NUMBER2_1028_R_K235_INCREMENTAL_RANK_099_R1"
)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=EVIDENCE_ROOT,
        help="the task evidence root named in the task packet",
    )
    args = parser.parse_args(argv)
    output_directory = args.output_directory.resolve()
    if output_directory != EVIDENCE_ROOT.resolve():
        parser.error("output directory must equal the task's authorized evidence root")

    ranking, comparison = build_from_fixed_paths()
    output_directory.mkdir(parents=True, exist_ok=True)
    ranking_path = output_directory / "ranking_115000099.json"
    comparison_path = output_directory / "window_comparison_115000099.json"
    _write_json(ranking_path, ranking)
    _write_json(comparison_path, comparison)

    summary = {
        "ranking_path": str(ranking_path),
        "window_comparison_path": str(comparison_path),
        "strategy_count": ranking["strategy_count"],
        "ranking_completeness": ranking["ranking_completeness"],
        "top3": {
            key: [row["strategy_id"] for row in value["top3"]]
            for key, value in ranking["rankings"].items()
        },
        "new_gap_cell_counts": ranking["new_gap_cell_counts"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
