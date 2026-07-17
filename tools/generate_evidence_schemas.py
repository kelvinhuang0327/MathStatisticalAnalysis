"""Deterministically export JSON Schema for the four evidence contract models.

Pydantic remains the enforcement engine; these exports are for external
consumers (documentation, potential future frontend type generation) and are
not re-validated against at runtime by ``lottolab.evidence.validator``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lottolab.evidence.models import (
    DatasetSnapshot,
    MetricDefinition,
    RankingPolicy,
    StrategyEvaluationEvidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_TARGETS: tuple[tuple[type[Any], Path], ...] = (
    (
        StrategyEvaluationEvidence,
        REPO_ROOT / "contracts/evidence/strategy_evaluation_evidence.schema.json",
    ),
    (DatasetSnapshot, REPO_ROOT / "contracts/evidence/dataset_snapshot.schema.json"),
    (RankingPolicy, REPO_ROOT / "contracts/evidence/ranking_policy.schema.json"),
    (MetricDefinition, REPO_ROOT / "contracts/evidence/metric_definition.schema.json"),
)


def render_schema(model_type: type[Any]) -> bytes:
    """Deterministic, sorted, compact JSON Schema bytes plus one trailing LF.

    JSON Schema documents may legitimately contain the JSON literal ``null``
    (e.g. ``"default": null`` for an Optional field), so this uses the LCJ-1
    *formatting* convention (sorted keys, compact separators, one trailing
    LF) without LCJ-1's stricter contract-document value-domain rule, which
    forbids null. That rule governs contract *instances*, not their schemas.
    """

    schema: dict[str, Any] = model_type.model_json_schema()
    text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return (text + "\n").encode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Detect stale generated files without writing them.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    stale: list[Path] = []
    for model_type, target in SCHEMA_TARGETS:
        rendered = render_schema(model_type)
        existing = target.read_bytes() if target.exists() else None
        if existing == rendered:
            continue
        if args.check:
            stale.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered)

    if args.check:
        if stale:
            for target in stale:
                print(f"STALE: {target.relative_to(REPO_ROOT)}")
            print(f"EVIDENCE_SCHEMA_CHECK_FAILED stale={len(stale)}")
            return 1
        print("EVIDENCE_SCHEMA_CHECK_PASS stale=0")
        return 0

    print(f"EVIDENCE_SCHEMA_GENERATED count={len(SCHEMA_TARGETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
