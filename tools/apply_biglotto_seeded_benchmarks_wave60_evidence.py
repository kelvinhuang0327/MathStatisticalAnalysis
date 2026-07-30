#!/usr/bin/env python3
"""Apply three wave-60 seeded benchmark backtests to the catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_seeded_benchmark_native_portfolios_wave60 import (
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "57897e5073fbeb796ad90df9ad67010d8001c14c775c554b2304c3d6c6e6fd88"
)
BASE_CATALOG_FILE_SHA256 = (
    "5034dea7d5f1e9b42b62a0291237ea103fe93d79617db4564bb735bbf4936138"
)
EXPECTED_EVIDENCE_SHA256 = (
    "e93a8759d40dbacc674546e2fca284ac14c728e31e74a91d6a9a1e974329033e"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SEEDED_BENCHMARKS_WAVE60_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_seeded_benchmarks_wave60_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 126,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 9,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 129,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 6,
}
EXPECTED_REPORT_SHA256 = (
    "0769459ec4aa11c3da4cc1b353eddf65bcc26daf75fc045218775d7fb4b4224b"
)
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    "tools/hybrid_integration_benchmark.py": {
        "3": 2128,
        "4": 6,
        "5": 8,
        "6": 6,
    },
    "tools/orthogonal_diversification_benchmark.py": {"4": 2148},
    "tools/zone_split_optimizer.py": {"0": 2145, "1": 3},
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-60 evidence is inconsistent."""


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
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CatalogOverlayError(f"{path}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise CatalogOverlayError(
            f"{path}: top level must be an object"
        )
    return (
        cast(dict[str, Any], parsed),
        hashlib.sha256(raw).hexdigest(),
    )


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
        or evidence.get("base_catalog_sha256")
        != BASE_CATALOG_SHA256
        or evidence.get("base_catalog_file_sha256")
        != BASE_CATALOG_FILE_SHA256
        or evidence.get("causal_protocol") != CAUSAL_PROTOCOL
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256") != EXPECTED_REPORT_SHA256
    ):
        raise CatalogOverlayError("wave-60 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-60 strategy evidence changed"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-60 method identity changed"
            )
        by_method[method_id] = row
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS):
        raise CatalogOverlayError("wave-60 method set changed")
    for method_id, strategy in by_method.items():
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        configuration_count = (
            LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        if (
            strategy.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[method_id]
            or strategy.get("execution_status_counts")
            != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
            or strategy.get("ok_execution_count") != 2148
            or strategy.get("closed_execution_count") != 1
            or strategy.get("candidate_k_distribution")
            != {"49": 2148}
            or strategy.get("combination_count_distribution")
            != {str(configuration_count): 2148}
            or strategy.get("native_ticket_count_distribution")
            != {str(native_count): 2148}
            or strategy.get(
                "native_duplicate_ticket_count_distribution"
            )
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or strategy.get("native_ticket_semantics")
            != NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
            or strategy.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
        ):
            raise CatalogOverlayError(
                f"wave-60 strategy evidence changed: {method_id}"
            )
    return by_method


def apply_wave60_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay three independently BACKTESTED benchmark methods."""

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
        raise CatalogOverlayError("wave-60 evidence file changed")
    strategy_evidence = _validate_evidence(evidence)

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

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = strategy_evidence[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-60 evidence leaves the validated universe"
            )
        native_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        configuration_count = (
            LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        duplicate_distribution = cast(
            dict[str, int],
            evidence_row[
                "native_duplicate_ticket_count_distribution"
            ],
        )
        record.update(
            {
                "candidate_k_semantics": (
                    "ORDERED20_INPUT_USES_FULL_49_LEGAL_NUMBER_DOMAIN_"
                    "DISTINCT_FROM_SOURCE_LOCAL_CONFIGURATION_COUNT_"
                    "NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "combination_count_semantics": (
                    "DECLARED_BIG_LOTTO_LOCAL_CONFIGURATION_COUNT_"
                    f"{configuration_count}_DISTINCT_FROM_CANDIDATE_K_"
                    "NATIVE_TICKET_COUNT_AND_ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen-runtime execution preserved the declared "
                    f"BIG_LOTTO local configuration order as {native_count} "
                    "positional native tickets for 2148 targets using only "
                    "each target's strictly earlier full history prefix; the "
                    "first target is explicitly closed because no prior "
                    "cutoff exists. Python and NumPy seed 42 are reset per "
                    "target before the source-order configuration block. "
                    "Candidate-K, local configuration count, native ticket "
                    "count, and ordered-20 remain distinct. Compact evidence "
                    f"SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "FROZEN_SOURCE_NATIVE_DUPLICATES_PRESERVED_BEFORE_"
                    "ORDERED_20_DERIVATION_DISTRIBUTION_"
                    + "_".join(
                        f"{key}:{value}"
                        for key, value in duplicate_distribution.items()
                    )
                ),
                "ticket_order_semantics": (
                    "FROZEN_BIG_LOTTO_NUM_BETS_BLOCK_THEN_DECLARED_"
                    "STRATEGY_THEN_POSITION_ORDER_BEFORE_ORDERED_20"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
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
                "SOURCE_NATIVE_WAVE60_HYBRID_ORTHOGONAL_AND_ZONE_"
                "SEEDED_BENCHMARK_FULL_PREFIX_CAUSAL_BACKTEST_PROOF"
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
    catalog = apply_wave60_evidence(
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
                "physical_file_sha256": hashlib.sha256(
                    payload
                ).hexdigest(),
                "status_counts": catalog["status_counts"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
