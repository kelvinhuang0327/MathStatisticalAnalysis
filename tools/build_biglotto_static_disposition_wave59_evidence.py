#!/usr/bin/env python3
"""Build frozen no-target-portfolio closure evidence for wave 59."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "4d4211355dc84791616a6f68f29dce3bbd293fa829426d8ed519618eb0fbf369"
)
BASE_CATALOG_FILE_SHA256 = (
    "33c4a9f1be363fab2e566b3931c58a2990ee52abf4199f0b8d4fe5076d020199"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE59_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V13"
REASON_CODE = (
    "OUTCOME_RANKING_SEARCH_HAS_NO_SOURCE_DEFINED_TARGET_PORTFOLIO_"
    "APPLICATION"
)
METHOD_ID = "ai_lab/scripts/automl_strategy_optimizer.py"
SOURCE_SHA256 = (
    "ad4b69c62db34be8d545987f1268c77b9401f132dee9c2852fc849bd03882d90"
)
REQUIRED_FRAGMENTS = (
    "result = self.evaluate_combination(combo, periods, window)",
    "results.sort(key=lambda x: (x['win_rate'], x['m4_count']), reverse=True)",
    "return results[:top_k]",
    "results_bl = optimizer_bl.search(",
)
DECISIVE_SOURCE_FACTS = (
    "The frozen search evaluates candidate method/window combinations "
    "against already-known target outcomes and returns only ranked "
    "aggregate metrics plus method names.",
    "Neither search nor main applies the selected winning configuration "
    "to a subsequent target or returns the tickets produced inside an "
    "evaluation loop.",
    "Choosing a leaderboard row and inventing a later portfolio "
    "application rule would create a new method rather than reproduce "
    "one source-defined target portfolio.",
)
STATUS_REASON = (
    "The frozen AutoML source is a retrospective configuration-ranking "
    "search. Its only public result is a list of aggregate leaderboard "
    "records, and the source never applies a selected row to emit a "
    "target-draw ticket portfolio."
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 73,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 10,
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-59 review."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(frozen_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EvidenceBuildError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _read_catalog(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    """Validate the frozen search/output boundary and build evidence."""

    catalog = _read_catalog(base_catalog_path)
    records = cast(list[object], catalog.get("records", []))
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed_candidate = cast(dict[str, Any], candidate)
        if typed_candidate.get("legacy_method_id") == METHOD_ID:
            record = typed_candidate
            break
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
    )
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
        )
        .decode("ascii")
        .strip()
    )
    if (
        hashlib.sha256(raw).hexdigest() != SOURCE_SHA256
        or record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_sha256") != SOURCE_SHA256
        or record.get("source_blob_id") != blob_id
        or record.get("source_byte_size") != len(raw)
    ):
        raise EvidenceBuildError("wave-59 method identity changed")
    text = raw.decode("utf-8")
    if any(fragment not in text for fragment in REQUIRED_FRAGMENTS):
        raise EvidenceBuildError("decisive source fact changed")
    return {
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": [
            {
                "decisive_source_facts": list(DECISIVE_SOURCE_FACTS),
                "legacy_method_id": METHOD_ID,
                "reason_code": REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": SOURCE_SHA256,
                "status_reason": STATUS_REASON,
            }
        ],
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "review_policy_version": REVIEW_POLICY_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    evidence = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
