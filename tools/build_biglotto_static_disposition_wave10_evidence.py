#!/usr/bin/env python3
"""Build frozen-source closure evidence for external HTTP-only predictors."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "9e3bd2d48407981805bcb763a523784420e9a7547fee609b9e423ed6baeda78d"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE10_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V3"
REASON_CODE = "EXTERNAL_HTTP_PREDICTION_RESPONSES_NOT_PRESERVED"
METHOD_SPECS: dict[str, dict[str, object]] = {
    "lottery_api/tools/backtest_6_bets.py": {
        "source_sha256": (
            "4b666aefe91e450bc04c201488954e60a9da401e587dbf848da93facf34cfabe"
        ),
        "required_fragments": (
            'API_URL = "http://localhost:8002/api/predict"',
            "response = requests.post(API_URL, json=payload, timeout=60)",
            'return response.json().get("numbers", [])',
        ),
        "decisive_source_facts": (
            "Every one of the six model tickets is obtained by POSTing to "
            "http://localhost:8002/api/predict.",
            "The frozen source stores only model names and request payloads; "
            "it does not contain the response tickets or identify a server "
            "build and model artifacts.",
            "A failed or unavailable HTTP response returns an empty list, so "
            "the file has no independent source-native ticket generator.",
        ),
        "status_reason": (
            "All six selections are opaque localhost API responses. The "
            "responses, serving build, trained artifacts, and reproducible "
            "model state were not preserved, so fabricating tickets would "
            "change the frozen method."
        ),
    },
    "lottery_api/tools/backtest_8_bets_2025.py": {
        "source_sha256": (
            "27f87ada05f997472a8397d32ef9c98e6fca6953bcab4e9feb7f279086cfe411"
        ),
        "required_fragments": (
            'API_BASE = "http://localhost:8002"',
            "def predict_8_bets(recent_count):",
            "response = requests.post(",
            'response = requests.get(f"{API_BASE}/api/history?lottery_type=BIG_LOTTO")',
        ),
        "decisive_source_facts": (
            "The eight model tickets come from localhost "
            "/api/predict-from-backend-eval responses.",
            "Even the draw history is fetched from the running HTTP service; "
            "the source passes only recent_count rather than the rolling "
            "history to the prediction endpoint.",
            "No response ledger, serving revision, model checkpoint, or "
            "random state is frozen with the method.",
        ),
        "status_reason": (
            "The portfolio is an orchestration of eight unversioned localhost "
            "API responses, not a self-contained ticket selector. Required "
            "responses and model-serving state are absent from frozen "
            "evidence."
        ),
    },
    "lottery_api/tools/backtest_8_bets_2025_v2.py": {
        "source_sha256": (
            "cd7dd52ca00c00de9d5dda39c6adda6360a0358f96c761fe99f1847a8480eb7a"
        ),
        "required_fragments": (
            'API_BASE = "http://localhost:8002"',
            "def predict_model_8_bets(model, history):",
            'f"{API_BASE}/api/predict",',
            "result = response.json()",
        ),
        "decisive_source_facts": (
            "For each model and history window the source POSTs a payload to "
            "localhost /api/predict and copies numbers from response JSON.",
            "The window schedule is preserved, but the eight model "
            "implementations, serving build, checkpoints, and response "
            "tickets are not pinned by this source.",
            "Its fallback only duplicates the last successful opaque response "
            "and cannot reconstruct a missing first response.",
        ),
        "status_reason": (
            "The window orchestration is visible but every native ticket "
            "depends on unpreserved localhost model responses. There is no "
            "source-native output to replay without inventing external state."
        ),
    },
    "lottery_api/tools/rolling_backtest_2025.py": {
        "source_sha256": (
            "e6949e10ba635562dd36db1ade146e8e12eb76432fefc894092ace803415f9f3"
        ),
        "required_fragments": (
            'API_BASE = "http://localhost:8002"',
            "def predict_with_history(model_name, history_data):",
            'f"{API_BASE}/api/predict-from-backend-eval?recent_count={recent_count}",',
            'return response.json().get("numbers", [])',
        ),
        "decisive_source_facts": (
            "predict_with_history does not execute a selector; it requests "
            "numbers from localhost /api/predict-from-backend-eval.",
            "The function reduces caller history to recent_count and relies on "
            "the server's own database and model state.",
            "No HTTP response, server build, checkpoint identity, or random "
            "state is preserved for causal ticket reconstruction.",
        ),
        "status_reason": (
            "The frozen driver delegates selection to an unversioned "
            "localhost service and does not transmit the claimed rolling "
            "history itself. Its native tickets cannot be reproduced from "
            "the frozen file and pinned draw history."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the closure review."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(
    frozen_root: Path,
    *arguments: str,
) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EvidenceBuildError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _read_catalog(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 34,
            "CLOSED_UNEXECUTABLE": 21,
            "DUPLICATE_ALIAS": 4,
            "OWNER_DECISION_REQUIRED": 162,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    catalog = _read_catalog(base_catalog_path)
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = row

    dispositions: list[dict[str, object]] = []
    for method_id, spec in METHOD_SPECS.items():
        record = record_by_method.get(method_id)
        expected_sha256 = cast(str, spec["source_sha256"])
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != expected_sha256
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if actual_sha256 != expected_sha256:
            raise EvidenceBuildError(
                f"frozen source SHA changed: {method_id}"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceBuildError(
                f"frozen source is not UTF-8: {method_id}"
            ) from exc
        required_fragments = cast(
            tuple[str, ...],
            spec["required_fragments"],
        )
        if any(fragment not in text for fragment in required_fragments):
            raise EvidenceBuildError(
                f"decisive frozen-source fact changed: {method_id}"
            )
        blob_id = (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            )
            .decode("ascii")
            .strip()
        )
        if (
            record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog frozen blob identity changed: {method_id}"
            )
        dispositions.append(
            {
                "decisive_source_facts": list(
                    cast(
                        tuple[str, ...],
                        spec["decisive_source_facts"],
                    )
                ),
                "legacy_method_id": method_id,
                "reason_code": REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": actual_sha256,
                "status_reason": spec["status_reason"],
            }
        )
    return {
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": dispositions,
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
    document = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "disposition_count": len(
                    cast(list[object], document["dispositions"])
                ),
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
