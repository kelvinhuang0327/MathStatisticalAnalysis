#!/usr/bin/env python3
"""Apply wave-65 evolution evidence to the full 221-strategy catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_evolution_native_portfolios_wave65 import (
    ACCELERATION_PROTOCOL,
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CLOSED_REASON,
    DETERMINISM_PROTOCOL,
    DRIVER_GENERATIONS,
    DRIVER_N_TEST,
    DRIVER_POPULATION_SIZE,
    ENGINE_SEED,
    EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION,
    EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION,
    FROZEN_SOURCE_COMMIT,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    CATALOG_POLICY_VERSION,
    CATALOG_SCHEMA_VERSION,
)

BASE_CATALOG_SHA256 = (
    "f66487d501864ee00f62a7cb237175600308120f7ad60df79681e812ae7e34e9"
)
BASE_CATALOG_FILE_SHA256 = (
    "36f2a7cf61f5e0c9d436154f8477ebd320d287e8601debbc47409ab45b1e2eb1"
)
EXPECTED_EVIDENCE_SHA256 = (
    "d99600e08f1160f3e750e1ea3656030a3cd77dfbef821de102ec666c5d2c3541"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_EVOLUTION_WAVE65_EVIDENCE_V1"
)
EVIDENCE_ARTIFACT_NAME = (
    "biglotto_legacy_evolution_wave65_evidence_v1.json"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 134,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 1,
}
EXPECTED_OUTPUT_STATUS_COUNTS = {
    "BACKTESTED": 135,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 0,
}
EXPECTED_REPORT_SHA256 = (
    "26f5a59b060aec251a3882ce31f8ee9c77ecb324e868013e425cb0f94dfe7a08"
)


class CatalogOverlayError(ValueError):
    """The catalog or wave-65 evidence is inconsistent."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise CatalogOverlayError(
            f"{path}: must be a regular non-symlink file"
        )
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


def _validate_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    rows = cast(list[object], evidence.get("strategies", []))
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
        or evidence.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
        or evidence.get("target_draw_count") != 2149
        or evidence.get("report_sha256") != EXPECTED_REPORT_SHA256
        or len(rows) != 1
        or not isinstance(rows[0], dict)
    ):
        raise CatalogOverlayError("wave-65 evidence identity changed")
    strategy = cast(dict[str, Any], rows[0])
    if (
        strategy.get("legacy_method_id") != METHOD_ID
        or strategy.get("source_sha256") != SOURCE_SHA256
        or strategy.get("execution_status_counts")
        != {
            "CLOSED_INSUFFICIENT_HISTORY": 501,
            "OK": 1648,
        }
        or strategy.get("ok_execution_count") != 1648
        or strategy.get("closed_execution_count") != 501
        or strategy.get("closed_reason_code_distribution")
        != {CLOSED_REASON: 501}
        or strategy.get("candidate_k_distribution")
        != {"NONE": 1648}
        or strategy.get("combination_count_distribution")
        != {"NONE": 1648}
        or strategy.get("native_ticket_count_distribution")
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or strategy.get(
            "native_duplicate_ticket_count_distribution"
        )
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or strategy.get("native_ticket_position_count") != 12959
        or strategy.get("native_ticket_semantics")
        != NATIVE_TICKET_SEMANTICS
        or strategy.get("native_ticket_order")
        != NATIVE_TICKET_ORDER
        or strategy.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or strategy.get("determinism_protocol")
        != DETERMINISM_PROTOCOL
        or strategy.get("source_random_state_explicit") is not True
        or strategy.get("driver_generations") != DRIVER_GENERATIONS
        or strategy.get("driver_population_size")
        != DRIVER_POPULATION_SIZE
        or strategy.get("driver_n_test") != DRIVER_N_TEST
        or strategy.get("engine_seed") != ENGINE_SEED
        or strategy.get("ticket_sequence_sha256")
        != TICKET_SEQUENCE_SHA256
    ):
        raise CatalogOverlayError("wave-65 strategy evidence changed")
    parity = cast(dict[str, object], evidence.get("parity", {}))
    if (
        parity.get("status") != "PASS"
        or parity.get("acceleration_protocol")
        != ACCELERATION_PROTOCOL
    ):
        raise CatalogOverlayError("wave-65 parity evidence changed")
    return strategy


def apply_wave65_evidence(
    *,
    base_catalog_path: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Overlay the final frozen evolution-engine causal backtest."""

    catalog, raw_catalog_sha256 = _read_json(base_catalog_path)
    evidence, evidence_sha256 = _read_json(evidence_path)
    if (
        raw_catalog_sha256 != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_schema_version")
        != CATALOG_SCHEMA_VERSION
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
        raise CatalogOverlayError("wave-65 evidence file changed")
    strategy = _validate_evidence(evidence)

    records = cast(list[object], catalog.get("records", []))
    record: dict[str, Any] | None = None
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        typed = cast(dict[str, Any], candidate)
        if typed.get("legacy_method_id") == METHOD_ID:
            record = typed
            break
    if (
        record is None
        or record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or record.get("source_commit") != FROZEN_SOURCE_COMMIT
        or record.get("source_sha256")
        != strategy.get("source_sha256")
    ):
        raise CatalogOverlayError(
            "wave-65 evidence leaves the validated universe"
        )
    record.update(
        {
            "candidate_k_semantics": (
                "NOT_USED_BY_SOURCE_EVOLUTION_ENGINE_DISTINCT_FROM_"
                "POPULATION_SIZE_NATIVE_TICKET_COUNT_AND_ORDERED_20"
            ),
            "combination_count_semantics": (
                "NOT_USED_BY_SOURCE_EVOLUTION_ENGINE_DISTINCT_FROM_"
                "STRATEGIES_TESTED_NATIVE_TICKET_COUNT_AND_ORDERED_20"
            ),
            "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
            "reproduction_status": "BACKTESTED",
            "status_reason": (
                "Exact frozen EvolutionEngine semantics were reproduced "
                "from the source driver defaults: seed 42, eight "
                "generations, population 50, and n_test 1500. Import-time "
                "script side effects were isolated while population, "
                "fitness, selection, crossover, mutation, generation, and "
                "report leaderboard order remained source-native. Every "
                "target sees only strictly earlier draws. The first 501 "
                "targets retain the source OOS evaluator closure and 1648 "
                "targets preserve 12959 ordered native ticket positions, "
                "including duplicates. Candidate-K and combination count "
                "are not used by this source and remain distinct from "
                "population, strategies tested, native ticket count, and "
                "ordered-20 count. Native cutoff-501 versus memoized parity "
                "and a byte-identical full parity combine rebuild passed. "
                f"Compact evidence SHA-256 is {evidence_sha256}."
            ),
            "ticket_duplicate_semantics": (
                "SOURCE_REPORT_1_LEADERBOARD_DUPLICATE_POSITIONS_"
                "PRESERVED_BEFORE_ORDERED_20_CONSTRUCTION"
            ),
            "ticket_order_semantics": (
                NATIVE_TICKET_ORDER
                + "_BEFORE_ORDERED_20_CONSTRUCTION"
            ),
            "unranked_reason": (
                "RANKED_BACKTEST_EVIDENCE_AVAILABLE_PARTIAL_COVERAGE"
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
                "SOURCE_NATIVE_WAVE65_EVOLUTION_ENGINE_FULL_PREFIX_"
                "CAUSAL_BACKTEST_PROOF"
            ),
        }
    )
    status_counts = Counter(
        cast(str, cast(dict[str, Any], item)["reproduction_status"])
        for item in records
    )
    normalized_status_counts = {
        status: status_counts[status]
        for status in EXPECTED_OUTPUT_STATUS_COUNTS
    }
    if normalized_status_counts != EXPECTED_OUTPUT_STATUS_COUNTS:
        raise CatalogOverlayError("output status counts changed")
    catalog["status_counts"] = dict(EXPECTED_OUTPUT_STATUS_COUNTS)
    catalog["full_universe_complete"] = True
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
    catalog = apply_wave65_evidence(
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
