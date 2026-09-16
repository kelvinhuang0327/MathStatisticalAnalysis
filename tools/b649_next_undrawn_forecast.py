"""Exercise the next-undrawn producer with a synthetic fixture store only.

Usage: uv run python tools/b649_next_undrawn_forecast.py --fixture INPUT.json
       --fixture-store OUTPUT_DIRECTORY
No production database, schedule source or strategy replay is composed here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lottolab.infrastructure.b649_next_undrawn_forecast import run_fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--fixture-store", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        stored = run_fixture(args.fixture, args.fixture_store)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.exit(2, f"fixture forecast rejected: {exc}\n")
    print(
        json.dumps(
            {
                "fixture_only": True,
                "bundle_id": stored.bundle.identity.bundle_id,
                "prediction_hash": stored.prediction.prediction_hash,
                "forecast": stored.bundle.payload(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
