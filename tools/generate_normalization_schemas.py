"""Deterministically export only the normalization manifest JSON Schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lottolab.normalization.models import DatasetNormalizationManifest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_TARGET = (
    REPO_ROOT / "contracts/normalization/dataset_normalization_manifest.schema.json"
)


def render_schema() -> bytes:
    schema: dict[str, Any] = DatasetNormalizationManifest.model_json_schema()
    text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return (text + "\n").encode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Detect a stale generated normalization schema without writing it.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rendered = render_schema()
    existing = SCHEMA_TARGET.read_bytes() if SCHEMA_TARGET.exists() else None
    stale = existing != rendered
    if args.check:
        if stale:
            print(f"STALE: {SCHEMA_TARGET.relative_to(REPO_ROOT)}")
            print("NORMALIZATION_SCHEMA_CHECK_FAILED stale=1")
            return 1
        print("NORMALIZATION_SCHEMA_CHECK_PASS stale=0")
        return 0
    if stale:
        SCHEMA_TARGET.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_TARGET.write_bytes(rendered)
    print("NORMALIZATION_SCHEMA_GENERATED count=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
