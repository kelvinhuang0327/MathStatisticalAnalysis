#!/usr/bin/env python3
"""Build checked evidence for the sixteenth BIG_LOTTO source-native batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    REPORT_SCHEMA_VERSION,
)
from lottolab.application.legacy_source_native_portfolios_wave16 import (
    CLOSED_SOURCE_NATIVE_WAVE16_METHODS,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD,
    HOT_COOCCURRENCE_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD,
    P270B_GEOMETRY_AUDIT_METHOD_ID,
    P282B_DEDUP_REPLAY_METHOD_ID,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE16_METHOD,
    SOURCE_NATIVE_WAVE16_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave16 import (
    MATERIALIZATION_SCHEMA_VERSION,
)
from verify_biglotto_legacy_source_native_wave16_parity import (
    FROZEN_SOURCE_COMMIT,
    PARITY_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE16_EVIDENCE_V1"
)
BASE_CATALOG_SHA256 = (
    "2924248b76d3ecbf43e237b6a29a002a7e2320baeeeed09f8f8e7ccbac1d8eff"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "4bb228b98745ccf947ecc52bdbc8c27e6bb9c9ac5881bfc3dc6637daa856be0c"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "927eb6c9816aee047a54a398e643e05980b371cb86e0de6954461641c4208327"
)
EXPECTED_REPORT_SHA256 = (
    "4489193609684ed5c0386c26215cad84269c4b9003824d2f779301576d323f2e"
)
EXPECTED_PARITY_SHA256 = (
    "e4f6194577f61fbefc4074b1f7b51e267fa1a1d13f24e7c6dcf576eca6cc6a79"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 40,
    "CLOSED_UNEXECUTABLE": 28,
    "DUPLICATE_ALIAS": 4,
    "OWNER_DECISION_REQUIRED": 149,
}
EXPECTED_PRE_OVERLAY_PROGRESS = {
    "backtested_count": 41,
    "closed_count": 28,
    "duplicate_alias_count": 4,
    "owner_decision_required_count": 148,
    "reproduced_count": 41,
    "total_strategy_count": 221,
    "uncompleted_count": 148,
}

_CLOSED_DISPOSITIONS = (
    {
        "decisive_source_facts": [
            "The binding source contract says No backtest and No strategy generation.",
            "The SQL reads only existing strategy_prediction_replays ticket-pool geometry.",
            "The rendered report explicitly states No strategy was generated.",
        ],
        "legacy_method_id": P270B_GEOMETRY_AUDIT_METHOD_ID,
        "reason_code": (
            "OUTCOME_BLIND_EXISTING_PORTFOLIO_GEOMETRY_AUDIT_"
            "WITHOUT_TICKET_GENERATION"
        ),
        "reproduction_status": "CLOSED_UNEXECUTABLE",
        "source_sha256": SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
            P270B_GEOMETRY_AUDIT_METHOD_ID
        ],
        "status_reason": (
            "The frozen program audits geometry and statistical power of "
            "tickets already stored in strategy_prediction_replays. Its "
            "binding contract and output both state that it runs no "
            "backtest and generates no strategy, so it has no independent "
            "native ticket portfolio to replay."
        ),
    },
    {
        "decisive_source_facts": [
            "Group C consumes frozen per-draw tickets already stored in "
            "strategy_prediction_replays.",
            "Group D only removes exact duplicates from Group C and never "
            "adds or replaces a ticket.",
            "The binding contract says no current or future live ticket is emitted or committed.",
        ],
        "legacy_method_id": P282B_DEDUP_REPLAY_METHOD_ID,
        "reason_code": (
            "RETROSPECTIVE_EXISTING_PORTFOLIO_DEDUP_FALSIFICATION_"
            "WITHOUT_LIVE_TICKET_OUTPUT"
        ),
        "reproduction_status": "CLOSED_UNEXECUTABLE",
        "source_sha256": SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
            P282B_DEDUP_REPLAY_METHOD_ID
        ],
        "status_reason": (
            "The frozen program compares already-stored replay portfolios "
            "with random baselines and an exact-deduplicated view. It "
            "explicitly emits no current or future live ticket, never "
            "replaces a removed ticket, and defines no independent "
            "target-draw selection method."
        ),
    },
)


class EvidenceBuildError(ValueError):
    """Wave-16 evidence inputs violate the frozen contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError(f"{path.name}: invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError(
            f"{path.name}: top level must be an object"
        )
    return cast(dict[str, Any], parsed), raw


def _validate_catalog(path: Path) -> None:
    catalog, _raw = _read_json(path)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    found: dict[str, dict[str, Any]] = {}
    expected = {
        HOT_COOCCURRENCE_METHOD_ID,
        *CLOSED_SOURCE_NATIVE_WAVE16_METHODS,
    }
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if type(method_id) is str and method_id in expected:
            found[method_id] = row
    if set(found) != expected or any(
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[method_id]
        for method_id, row in found.items()
    ):
        raise EvidenceBuildError("wave-16 catalog identities changed")


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or document.get("dataset_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", [])))
        != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions_raw = document.get("executions")
    if not isinstance(executions_raw, list):
        raise EvidenceBuildError("full input executions are missing")
    statuses: Counter[str] = Counter()
    candidate_k_values: set[int] = set()
    for candidate in cast(list[object], executions_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        status = row.get("status")
        if type(status) is not str:
            raise EvidenceBuildError("execution status is invalid")
        statuses[status] += 1
        if status != "OK":
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        candidate_k = row.get("candidate_k")
        if type(candidate_k) is not int:
            raise EvidenceBuildError("candidate-K evidence changed")
        candidate_k_values.add(candidate_k)
        if (
            native.get("legacy_method_id")
            != HOT_COOCCURRENCE_METHOD_ID
            or row.get("native_ticket_count") != 1
            or native.get("candidate_k") is not None
            or row.get("combination_count") != 1
            or native.get("combination_count") is not None
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                    HOT_COOCCURRENCE_METHOD_ID
                ]
            ]
            or len(cast(list[object], row["ordered_portfolio"]))
            != 20
        ):
            raise EvidenceBuildError("native execution evidence changed")
    if dict(sorted(statuses.items())) != {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 2148,
    } or candidate_k_values != {6, 11, 16, 19, 20}:
        raise EvidenceBuildError("execution status evidence changed")
    return {
        "candidate_k_observed_values": sorted(candidate_k_values),
        "closed_status_counts": {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
        },
        "combination_count": 1,
        "legacy_method_id": HOT_COOCCURRENCE_METHOD_ID,
        "minimum_history_draws": 1,
        "native_ticket_count": 1,
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE16_METHOD[
                HOT_COOCCURRENCE_METHOD_ID
            ]
        ),
        "ok_execution_count": 2148,
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE16_METHOD[
                HOT_COOCCURRENCE_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
                HOT_COOCCURRENCE_METHOD_ID
            ]
        ),
    }


def _validate_report(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or document.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or document.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or document.get("catalog_sha256") != BASE_CATALOG_SHA256
        or document.get("input_raw_sha256")
        != EXPECTED_INPUT_SHA256
        or document.get("report_sha256") != EXPECTED_REPORT_SHA256
        or document.get("progress") != EXPECTED_PRE_OVERLAY_PROGRESS
        or document.get("target_draw_count") != 2149
    ):
        raise EvidenceBuildError("full report identity changed")
    return {
        "artifact_sha256": EXPECTED_REPORT_FILE_SHA256,
        "internal_report_sha256": EXPECTED_REPORT_SHA256,
        "progress": EXPECTED_PRE_OVERLAY_PROGRESS,
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    support_raw = document.get("support_artifacts")
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("source_native_protocol")
        != SOURCE_NATIVE_WAVE16_PROTOCOL
        or document.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
            HOT_COOCCURRENCE_METHOD_ID
        ]
        or document.get("database_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("case_count") != 4
        or document.get("status") != "PASS"
        or not isinstance(support_raw, list)
        or len(cast(list[object], support_raw)) != 1
    ):
        raise EvidenceBuildError("frozen-source parity changed")
    return {
        "artifact_sha256": EXPECTED_PARITY_SHA256,
        "case_count": 4,
        "runtime_dependency_versions": (
            document["runtime_dependency_versions"]
        ),
        "status": "PASS",
        "support_artifacts": support_raw,
    }


def build_evidence(
    *,
    base_catalog_path: Path,
    input_a_path: Path,
    input_b_path: Path,
    report_a_path: Path,
    report_b_path: Path,
    parity_path: Path,
) -> dict[str, object]:
    _validate_catalog(base_catalog_path)
    input_a, input_a_raw = _read_json(input_a_path)
    _input_b, input_b_raw = _read_json(input_b_path)
    if input_a_raw != input_b_raw:
        raise EvidenceBuildError("full input double-run differs")
    strategy = _validate_input(input_a, input_a_raw)
    report_a, report_a_raw = _read_json(report_a_path)
    _report_b, report_b_raw = _read_json(report_b_path)
    if report_a_raw != report_b_raw:
        raise EvidenceBuildError("full report double-run differs")
    report = _validate_report(report_a, report_a_raw)
    parity, parity_raw = _read_json(parity_path)
    parity_summary = _validate_parity(parity, parity_raw)
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "closed_dispositions": list(_CLOSED_DISPOSITIONS),
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "full_input": {
            "artifact_sha256": EXPECTED_INPUT_SHA256,
            "execution_count": 2149,
            "status_counts": {
                "CLOSED_INSUFFICIENT_HISTORY": 1,
                "OK": 2148,
            },
            "target_draw_count": 2149,
        },
        "full_report": report,
        "parity": parity_summary,
        "port_protocol": SOURCE_NATIVE_WAVE16_PROTOCOL,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "strategies": [strategy],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-a", required=True, type=Path)
    parser.add_argument("--input-b", required=True, type=Path)
    parser.add_argument("--report-a", required=True, type=Path)
    parser.add_argument("--report-b", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        input_a_path=args.input_a,
        input_b_path=args.input_b,
        report_a_path=args.report_a,
        report_b_path=args.report_b,
        parity_path=args.parity,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "closed_disposition_count": len(_CLOSED_DISPOSITIONS),
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
                "strategy_count": 1,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
