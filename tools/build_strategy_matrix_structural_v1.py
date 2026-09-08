"""Build the immutable structural Matrix projection from the three pinned reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lottolab.infrastructure.strategy_matrix_structural_projection_builder import (
    StrategyMatrixStructuralBuildError,
    build_strategy_matrix_structural_projection_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the checksum-pinned structural Matrix projection. All three "
            "input reports are explicit paths; no source discovery occurs."
        )
    )
    parser.add_argument("--metric-surface", required=True, type=Path)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New output path. Existing files are never overwritten.",
    )
    arguments = parser.parse_args(argv)
    try:
        payload = build_strategy_matrix_structural_projection_bytes(
            metric_surface_path=arguments.metric_surface,
            matrix_path=arguments.matrix,
            ledger_path=arguments.ledger,
        )
        with arguments.output.open("xb") as handle:
            handle.write(payload)
    except (StrategyMatrixStructuralBuildError, FileExistsError, OSError) as exc:
        print(f"structural Matrix projection build failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
