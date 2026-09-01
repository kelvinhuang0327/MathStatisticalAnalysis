"""Build the immutable B649 aggregate-history resource from explicit reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    B649ProjectionBuildError,
    build_b649_k2_k3_projection_bytes,
    build_b649_projection_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a checksum-pinned B649 aggregate projection. Every --report "
            "or --replay-input is explicit; no source discovery occurs."
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
        "--source-projection",
        type=Path,
        help="Pinned V2 projection extended by exact-native K2/K3 metrics.",
    )
    parser.add_argument(
        "--replay-input",
        action="append",
        default=[],
        type=Path,
        help="Canonical materialized replay input; repeat for every source batch.",
    )
    parser.add_argument(
        "--dataset-source",
        type=Path,
        help="Canonical replay-universe source file whose SHA-256 is pinned.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New output path. Existing files are never overwritten.",
    )
    arguments = parser.parse_args(argv)
    try:
        successor_requested = any(
            (
                arguments.source_projection is not None,
                bool(arguments.replay_input),
                arguments.dataset_source is not None,
            )
        )
        if successor_requested:
            if arguments.report:
                parser.error(
                    "--report cannot be combined with exact-native successor inputs"
                )
            if (
                arguments.source_projection is None
                or not arguments.replay_input
                or arguments.dataset_source is None
            ):
                parser.error(
                    "exact-native successor mode requires --source-projection, "
                    "--dataset-source, and at least one --replay-input"
                )
            payload = build_b649_k2_k3_projection_bytes(
                source_projection_path=arguments.source_projection,
                replay_input_paths=tuple(arguments.replay_input),
                dataset_source_path=arguments.dataset_source,
            )
        else:
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
