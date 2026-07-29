#!/usr/bin/env python3
"""Apply wave-38 unbound stochastic native-selection closures."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "01c54ea1d5ce2f578663d4639de5d2f12f6dc39b6a2158f4118a03cdc253753a"
)
BASE_CATALOG_FILE_SHA256 = (
    "4e47c7c8bb4c6160140f8d2578e594a14c7a86afc508ef3482bff872c1c33223"
)
EXPECTED_EVIDENCE_SHA256 = (
    "c1a4e85a706d3a5390da41e21153e1c34e0f5361c144eb49ef29e5bcf2bb982f"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE38_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V10"
REASON_CODE = (
    "UNBOUND_STOCHASTIC_NATIVE_SELECTION_WITHOUT_FROZEN_PRESTATE"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_static_disposition_wave38_evidence_v1.json"
)
CLOSED_METHODS = {
    "lottery_api/models/dynamic_ensemble_predictor.py": (
        "9d1dce6311e2ba6f49103e5348c9a6a8ec182598cbe8bec158208890caea0e54"
    ),
    "lottery_api/models/enhanced_predictor.py": (
        "7bd110ea9eab867f26bf63fe6e1f2857fdbd0effd844c3e2c26eb83a9f444592"
    ),
    "lottery_api/models/mcts_portfolio_optimizer.py": (
        "2475434b6ed2dbab48e8e06a4cd40454250e6c24d2eee9ad9a4c8eaa3548f503"
    ),
    "lottery_api/models/transformer_model.py": (
        "58662b208fee454ce3a93db4ae820863bceff14a60c1a6e3b0b4870c25ec5c5a"
    ),
    "lottery_api/models/multi_bet_optimizer.py": (
        "fd171e7f2a121f5e3b25063377694706c7acabf5c644ea9b7dd707051cc795ef"
    ),
    "tools/backtest/benchmark_dual_bet.py": (
        "0d6d2be1b3a21c95d5e919fb55e2cb9475f69a19181997d5a031c71b50e49785"
    ),
    "tools/benchmark_new_strategies.py": (
        "b297ac69391ac99f42f348b08da46c31c6ddcc0baa6bf2196511ad07f1535bd5"
    ),
    "tools/predict_biglotto_6bets_optimized.py": (
        "f8bf1f0ecd742544d74a17c0edbd44bfdd54f8a9879813feb89fcf7ff41f6ae7"
    ),
    "tools/strategy_leaderboard.py": (
        "5af2848b20597058819a49fb34a5fd5c3c9a2f26a91d89232ff8b177e510a334"
    ),
}
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 45,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 93,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 54,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 84,
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-38 evidence is inconsistent."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(document, dict):
        raise CatalogOverlayError(f"{path}: top level must be an object")
    return cast(dict[str, Any], document), hashlib.sha256(raw).hexdigest()


def _catalog_hash(document: dict[str, Any]) -> str:
    reduced = {
        key: value
        for key, value in document.items()
        if key != "catalog_sha256"
    }
    return hashlib.sha256(_canonical_bytes(reduced)).hexdigest()


def _validate_evidence(
    evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if (
        evidence.get("evidence_schema_version")
        != EVIDENCE_SCHEMA_VERSION
        or evidence.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or evidence.get("review_policy_version")
        != REVIEW_POLICY_VERSION
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
    ):
        raise CatalogOverlayError("wave-38 evidence identity changed")
    rows_raw = evidence.get("dispositions")
    if not isinstance(rows_raw, list):
        raise CatalogOverlayError(
            "wave-38 evidence dispositions must be a list"
        )
    rows = cast(list[object], rows_raw)
    if len(rows) != len(CLOSED_METHODS):
        raise CatalogOverlayError(
            "wave-38 evidence disposition count changed"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-38 disposition must be an object"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is not str or method_id not in CLOSED_METHODS:
            raise CatalogOverlayError(
                "wave-38 disposition method changed"
            )
        facts_raw = row.get("decisive_source_facts")
        facts = (
            cast(list[object], facts_raw)
            if isinstance(facts_raw, list)
            else []
        )
        if (
            method_id in by_method
            or row.get("reproduction_status")
            != "CLOSED_UNEXECUTABLE"
            or row.get("reason_code") != REASON_CODE
            or row.get("source_sha256") != CLOSED_METHODS[method_id]
            or type(row.get("source_blob_id")) is not str
            or type(row.get("source_byte_size")) is not int
            or len(facts) != 3
            or type(row.get("status_reason")) is not str
        ):
            raise CatalogOverlayError(
                "wave-38 disposition identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(CLOSED_METHODS):
        raise CatalogOverlayError("wave-38 evidence omits a closure")
    return by_method


def apply_wave38_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
        or catalog.get("catalog_policy_version")
        != CATALOG_POLICY_VERSION
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or _catalog_hash(catalog) != BASE_CATALOG_SHA256
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
    ):
        raise CatalogOverlayError("base catalog identity changed")
    if evidence_sha256 != EXPECTED_EVIDENCE_SHA256:
        raise CatalogOverlayError("wave-38 evidence file changed")
    dispositions = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError("base catalog record is invalid")
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")

    for method_id, evidence_row in dispositions.items():
        record = record_by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
            or record.get("source_blob_id")
            != evidence_row.get("source_blob_id")
            or record.get("source_byte_size")
            != evidence_row.get("source_byte_size")
        ):
            raise CatalogOverlayError(
                "wave-38 closure leaves the validated universe"
            )
        record.update(
            {
                "candidate_k_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "combination_count_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "native_ticket_semantics": (
                    "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_"
                    "STOCHASTIC_SELECTION_PRESTATE_WAS_NOT_BOUND_OR_"
                    "SERIALIZED"
                ),
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "status_reason": (
                    f"{evidence_row['status_reason']} Frozen-source "
                    "wave-38 disposition evidence SHA-256 is "
                    f"{evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "ticket_order_semantics": (
                    "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
                ),
                "unranked_reason": (
                    f"CLOSED_UNEXECUTABLE:{REASON_CODE}"
                ),
            }
        )

    source_artifacts = cast(
        list[object],
        catalog.get("source_artifacts", []),
    )
    source_artifacts.append(
        {
            "artifact_name": EVIDENCE_ARTIFACT_NAME,
            "artifact_sha256": evidence_sha256,
            "evidence_role": (
                "STATIC_DISPOSITION_WAVE38_UNBOUND_STOCHASTIC_"
                "NATIVE_SELECTION_REVIEW"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], item)["reproduction_status"])
        for item in records
    )
    if dict(status_counts) != EXPECTED_OUTPUT_STATUS_COUNTS:
        raise CatalogOverlayError("output status counts changed")
    catalog["status_counts"] = dict(EXPECTED_OUTPUT_STATUS_COUNTS)
    catalog["catalog_sha256"] = _catalog_hash(catalog)
    return cast(dict[str, object], catalog)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    catalog = apply_wave38_evidence(
        base_catalog_path=args.base_catalog,
        evidence_path=args.evidence,
    )
    payload = _canonical_bytes(catalog) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "catalog_sha256": catalog["catalog_sha256"],
                "output_file": str(args.output_file),
                "physical_file_sha256": hashlib.sha256(payload).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
