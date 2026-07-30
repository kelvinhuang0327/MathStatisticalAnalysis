#!/usr/bin/env python3
"""Apply wave-26 source-native evidence to the full BIG_LOTTO catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_source_native_portfolios_wave26 import (
    DMS_METHOD_ID,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD,
    PCE_METHOD_ID,
    SMH_CLOSED_METHOD_ID,
    SMH_CLOSED_REASON_CODE,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "ae4b21d03d6c4c56b29d6ae53292d2f85671fa8ab07fdf36e867f2fb62162957"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE26_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
EXPECTED_EVIDENCE_SHA256 = (
    "2fdfc4daf2bed05615ba8f664959960a6c9e64379501bd739557dfda2beae980"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_source_native_wave26_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 58,
    "CLOSED_UNEXECUTABLE": 37,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 121,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 63,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 115,
}
EXPECTED_OK_COUNTS = {
    "tools/test_ces.py": 2148,
    "tools/test_dms.py": 2129,
    "tools/test_greedy_optimizer.py": 2148,
    "tools/test_mwsc.py": 2148,
    "tools/test_pce.py": 2148,
}
EXPECTED_DUPLICATE_DISTRIBUTIONS = {
    "tools/test_ces.py": {"0": 2148},
    "tools/test_dms.py": {"0": 2122, "1": 6, "2": 1},
    "tools/test_greedy_optimizer.py": {"0": 2148},
    "tools/test_mwsc.py": {"0": 2148},
    "tools/test_pce.py": {"0": 2148},
}
EXPECTED_CLOSED_COUNTS = {
    method_id: 2149 - ok_count
    for method_id, ok_count in EXPECTED_OK_COUNTS.items()
}


class CatalogOverlayError(ValueError):
    """The catalog or wave-26 evidence is inconsistent."""


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
        raise CatalogOverlayError(f"{path}: top level must be an object")
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
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256")
        != "5b6e44e5ea9ee47c588345af81beb1612bd263d5a957537de9c7f5518e49fa99"
    ):
        raise CatalogOverlayError("wave-26 evidence identity changed")
    rows = cast(list[object], evidence.get("strategies", []))
    if len(rows) != 5:
        raise CatalogOverlayError(
            "wave-26 evidence must contain five strategies"
        )
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in rows:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "wave-26 strategy evidence is invalid"
            )
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if not isinstance(method_id, str):
            raise CatalogOverlayError(
                "wave-26 strategy method is invalid"
            )
        by_method[method_id] = row
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
        row = by_method.get(method_id)
        if (
            row is None
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                method_id
            ]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                method_id
            ]
            or row.get("source_method_combination_count")
            != SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE26_METHOD[
                method_id
            ]
            or row.get("closed_execution_count")
            != EXPECTED_CLOSED_COUNTS[method_id]
            or row.get("ok_execution_count")
            != EXPECTED_OK_COUNTS[method_id]
            or row.get("native_duplicate_ticket_count_distribution")
            != EXPECTED_DUPLICATE_DISTRIBUTIONS[method_id]
            or not isinstance(row.get("candidate_k_distribution"), dict)
            or not isinstance(row.get("execution_status_counts"), dict)
            or not isinstance(row.get("kill_count_distribution"), dict)
        ):
            raise CatalogOverlayError(
                "wave-26 strategy identity changed"
            )
    parity = cast(dict[str, Any], evidence.get("parity", {}))
    static_dispositions = cast(
        list[object], evidence.get("static_dispositions", [])
    )
    if (
        parity.get("case_count") != 165
        or parity.get("closed_parity_case_count") != 19
        or parity.get("status") != "PASS"
        or not isinstance(parity.get("source_artifacts"), list)
        or not isinstance(parity.get("support_artifacts"), list)
        or static_dispositions
        != [
            {
                "legacy_method_id": SMH_CLOSED_METHOD_ID,
                "random_sample_call_count": 2,
                "random_state_binding_calls": [],
                "reason_code": SMH_CLOSED_REASON_CODE,
                "source_sha256": (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        SMH_CLOSED_METHOD_ID
                    ]
                ),
                "status": "CLOSED_UNEXECUTABLE",
            }
        ]
    ):
        raise CatalogOverlayError("wave-26 parity evidence changed")
    return by_method


def apply_wave26_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    catalog, _raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        catalog.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION
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
        raise CatalogOverlayError("wave-26 evidence file changed")
    evidence_by_method = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise CatalogOverlayError(
                "base catalog record is invalid"
            )
        record = cast(dict[str, Any], candidate)
        method_id = record.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = record
    if len(record_by_method) != 221:
        raise CatalogOverlayError("base catalog records changed")

    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE26_METHODS:
        record = record_by_method.get(method_id)
        evidence_row = evidence_by_method[method_id]
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_commit") != FROZEN_SOURCE_COMMIT
            or record.get("source_sha256")
            != evidence_row.get("source_sha256")
        ):
            raise CatalogOverlayError(
                "wave-26 evidence leaves the validated universe"
            )
        ok_count = EXPECTED_OK_COUNTS[method_id]
        closed_count = EXPECTED_CLOSED_COUNTS[method_id]
        candidate_semantics = (
            "NOT_APPLICABLE_NO_DECLARED_PRE_TICKET_CANDIDATE_POOL"
            if method_id in (DMS_METHOD_ID, PCE_METHOD_ID)
            else (
                "EXECUTION_SPECIFIC_FROZEN_RANKED_NUMBER_POOL_LENGTH_"
                "DISTINCT_FROM_NATIVE_TICKET_COUNT"
            )
        )
        record.update(
            {
                "candidate_k_semantics": candidate_semantics,
                "combination_count_semantics": (
                    "FROZEN_SOURCE_PREDICTOR_COMPONENT_COUNT_"
                    "DISTINCT_FROM_CANDIDATE_K_NATIVE_TICKETS_AND_"
                    "ORDERED_20"
                ),
                "native_ticket_semantics": (
                    "FROZEN_SOURCE_NATIVE_"
                    + NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE26_METHOD[
                        method_id
                    ]
                ),
                "reproduction_status": "BACKTESTED",
                "status_reason": (
                    "Frozen AST class parity covered the first 30 causal "
                    "cutoffs plus 50, 150, and 2148 draws, preserving "
                    "stable Counter/sort tie order, constraint scoring, "
                    "dynamic method-audit order, multi-window slicing, "
                    "pair consensus, native positions, and duplicates. "
                    f"{ok_count} causal executions completed and "
                    f"{closed_count} insufficient-history closures "
                    "remained explicit. Compact "
                    f"evidence SHA-256 is {evidence_sha256}."
                ),
                "ticket_duplicate_semantics": (
                    "PRESERVE_ALL_FROZEN_POSITIONAL_TICKETS_INCLUDING_"
                    "ANY_SOURCE_DUPLICATES"
                ),
                "ticket_order_semantics": (
                    "FROZEN_SOURCE_ENTRYPOINT_POSITIONAL_ORDER_BEFORE_"
                    "ORDERED_20_CONSTRUCTION"
                ),
                "unranked_reason": (
                    "RANKED_BACKTEST_EVIDENCE_AVAILABLE"
                ),
            }
        )

    smh_record = record_by_method.get(SMH_CLOSED_METHOD_ID)
    if (
        smh_record is None
        or smh_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or smh_record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or smh_record.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[
            SMH_CLOSED_METHOD_ID
        ]
    ):
        raise CatalogOverlayError(
            "wave-26 SMH disposition leaves the validated universe"
        )
    smh_record.update(
        {
            "candidate_k_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "combination_count_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "native_ticket_semantics": (
                "NO_REPRODUCIBLE_FROZEN_NATIVE_TICKETS_BECAUSE_"
                "MODULE_GLOBAL_RANDOM_STATE_WAS_NOT_BOUND_OR_SERIALIZED"
            ),
            "reproduction_status": "CLOSED_UNEXECUTABLE",
            "status_reason": (
                "The frozen SMH entrypoint calls module-global "
                "random.sample twice but neither binds a seed/state nor "
                "accepts one as input. No historical RNG pre-state was "
                "serialized, so assigning a new seed would create a new "
                "method rather than reproduce the frozen native tickets. "
                f"Compact evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "ticket_order_semantics": (
                "NOT_APPLICABLE_CLOSED_UNEXECUTABLE"
            ),
            "unranked_reason": SMH_CLOSED_REASON_CODE,
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
                "SOURCE_NATIVE_WAVE26_CONSTRAINT_DYNAMIC_CONSENSUS_"
                "CAUSAL_BACKTEST_AND_UNSEEDED_RNG_DISPOSITION"
            ),
        }
    )
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
    catalog = apply_wave26_evidence(
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
