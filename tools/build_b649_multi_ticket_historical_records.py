"""Build the immutable B649 aggregate-history resource from explicit reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lottolab.infrastructure.biglotto_multi_ticket_projection_builder import (
    B649ProjectionBuildError,
    build_b649_k2_k3_projection_bytes,
    build_b649_k5_projection_bytes,
    build_b649_k10_projection_bytes,
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
    parser.add_argument("--k5-manifest", type=Path)
    parser.add_argument("--k5-evidence", type=Path)
    parser.add_argument("--k5-ranking", type=Path)
    parser.add_argument("--k10-manifest", type=Path)
    parser.add_argument("--k10-evidence", type=Path)
    parser.add_argument("--k10-ranking", type=Path)
    arguments = parser.parse_args(argv)
    try:
        successor_requested = any(
            (
                arguments.source_projection is not None,
                bool(arguments.replay_input),
                arguments.dataset_source is not None,
            )
        )
        k10_requested = any((arguments.k10_manifest, arguments.k10_evidence, arguments.k10_ranking))
        k5_requested = any((arguments.k5_manifest, arguments.k5_evidence, arguments.k5_ranking))
        if k5_requested:
            if k10_requested or successor_requested or arguments.report:
                parser.error("K5 materialization cannot be combined with other build modes")
            if not all((arguments.k5_manifest, arguments.k5_evidence, arguments.k5_ranking)):
                parser.error("K5 requires --k5-manifest, --k5-evidence and --k5-ranking")
            payload = build_b649_k5_projection_bytes(
                arguments.k5_manifest, arguments.k5_evidence, arguments.k5_ranking,
            )
        elif k10_requested:
            if successor_requested or arguments.report:
                parser.error("K10 materialization cannot be combined with other build modes")
            if not all((arguments.k10_manifest, arguments.k10_evidence, arguments.k10_ranking)):
                parser.error("K10 requires --k10-manifest, --k10-evidence and --k10-ranking")
            payload = build_b649_k10_projection_bytes(
                arguments.k10_manifest,
                arguments.k10_evidence,
                arguments.k10_ranking,
            )
        elif successor_requested:
            if arguments.report:
                parser.error("--report cannot be combined with exact-native successor inputs")
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
