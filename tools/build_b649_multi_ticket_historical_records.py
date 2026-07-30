"""Build the immutable B649 aggregate-history resource from explicit reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    B649ProjectionBuildError,
    build_b649_projection_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a checksum-pinned B649 aggregate projection. Every --report "
            "is explicit; no report discovery or backtest execution occurs."
        )
    )
    parser.add_argument(
        "--report",
        action="append",
        default=[],
        type=Path,
        help="Exact report JSON path; repeat for every pinned source report.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New output path. Existing files are never overwritten.",
    )
    arguments = parser.parse_args(argv)
    try:
        payload = build_b649_projection_bytes(tuple(arguments.report))
        with arguments.output.open("xb") as handle:
            handle.write(payload)
    except (B649ProjectionBuildError, FileExistsError, OSError) as exc:
        print(f"projection build failed: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
