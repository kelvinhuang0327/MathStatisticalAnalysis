"""One-shot executable CLI entrypoint for BIG_LOTTO prospective campaign seals.

Usage:
    python -m tools.b649_prospective_campaign_seal \\
        --campaign-ordinal 2 \\
        --target-draw 115000087

    # With explicit paths
    python -m tools.b649_prospective_campaign_seal \\
        --campaign-ordinal 2 \\
        --target-draw 115000087 \\
        --campaign-spec path/to/campaign_spec.json \\
        --draw-seals-dir path/to/draw_seals/
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from lottolab.application.b649_prospective_campaign_seal import (
    EXPECTED_CAMPAIGN_ID,
    B649CampaignSealResult,
    CampaignSealRunnerError,
    run_b649_prospective_campaign_seal,
)

_DEFAULT_SPEC_PATH = Path(
    ".task-data/BRANCH2_TABU7_FIXED_K10_VS_10BET_PROSPECTIVE_104DRAW_CAMPAIGN_R1/campaign_spec.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BIG_LOTTO 104-draw prospective campaign seal runner for ordinals 2..104"
    )
    parser.add_argument(
        "--campaign-id",
        type=str,
        default=EXPECTED_CAMPAIGN_ID,
        help="Campaign identifier (must match campaign spec authority)",
    )
    parser.add_argument(
        "--campaign-ordinal",
        type=int,
        required=True,
        help="Campaign ordinal (must be an integer 2..104)",
    )
    parser.add_argument(
        "--target-draw",
        type=str,
        required=True,
        help="Target BIG_LOTTO draw number (e.g. 115000087)",
    )
    parser.add_argument(
        "--campaign-spec",
        type=Path,
        default=_DEFAULT_SPEC_PATH,
        help="Path to frozen campaign_spec.json",
    )
    parser.add_argument(
        "--draw-seals-dir",
        type=Path,
        default=None,
        help="Directory to store draw seals (defaults to path in campaign_spec)",
    )
    parser.add_argument(
        "--data-directory",
        type=Path,
        default=None,
        help="Override SQLite local data directory",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for relative path resolution",
    )
    return parser


def main(
    argv: list[str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result: B649CampaignSealResult = run_b649_prospective_campaign_seal(
            campaign_id=args.campaign_id,
            campaign_ordinal=args.campaign_ordinal,
            target_draw=args.target_draw,
            campaign_spec_path=args.campaign_spec,
            draw_seals_dir=args.draw_seals_dir,
            data_directory=args.data_directory,
            repo_root=args.repo_root,
            clock=clock,
        )
        receipt = {
            "status": result.status.value,
            "campaign_id": result.campaign_id,
            "campaign_ordinal": result.campaign_ordinal,
            "target_draw": result.target_draw,
            "history_cutoff_draw": result.history_cutoff_draw,
            "seal_path": str(result.seal_path),
            "seal_sha256": result.seal_sha256,
            "canonical_prediction_record_sha256": result.canonical_prediction_record_sha256,
        }
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0
    except CampaignSealRunnerError as exc:
        sys.stderr.write(f"ERROR: {type(exc).__name__}: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
