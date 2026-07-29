#!/usr/bin/env python3
"""Build compact evidence for the wave-61 five-bet causal replay."""

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
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_five_bet_native_portfolios_wave61 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE61_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_five_bet_native_batch_import_wave61 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_FIVE_BET_WAVE61_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_FIVE_BET_WAVE61_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "d3d3aaa7b8b0b8b6dff39ea900440944812cdb5118f90c20a9dd02c733be77f9"
)
BASE_CATALOG_FILE_SHA256 = (
    "21e229c8994b292dc7be08922c15113094d3f19e8d675282ca388a6d23ceeb44"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 129,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 6,
}
EXPECTED_PROGRESS = {
    "backtested_count": 130,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 5,
    "reproduced_count": 130,
    "total_strategy_count": 221,
    "uncompleted_count": 5,
}
EXPECTED_INPUT_FILE_SHA256 = (
    "ddbb9ff87252e0844cb0deb40d7a1fa02d825ed11e07e6b931bf1877182717d3"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "2accbe2596a33d767833f375b37c4715a8f9272c5159df4c295eb1a886729c32"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "47d27bbd00eefe9525d2c028154727b919850a0658ae0b1fb78246a07f100949"
)
EXPECTED_PARITY_SHA256 = (
    "0de9a589013df3748f0b9b8d596a470d00b78d5ccf11f6f54e04563d2762c88e"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "8eb95f4a9e4d34d7f0612c5df37d0a15239012d01a9aad1ceaec4de3ea237a10"
)
EXPECTED_REPORT_SHA256 = (
    "ea0950f3f9f46ecbf29f12c54e95540a4641f76565d82ae1d940b081ad830181"
)
EXPECTED_OK_SEQUENCE_SHA256 = (
    "226f676ff85288bf8adf0198a92640144a46da04e88315252bd56733a3983af1"
)
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "ee201a480ba566ae1b3ae7faf6b9d52ee9cc1c6c5409a1908ff80731f716f198"
    ),
    "biglotto_execution_audit.csv": (
        "01e0bf90f7d2813b478b15fbf9a3a59e2b943580bc651a3ec4de3c265a56d714"
    ),
    "biglotto_full_rankings.csv": (
        "bed17da19a9cb4f19f0216a5066d52580a11de67dac80c1500e17f84ff8cc63c"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "8eb95f4a9e4d34d7f0612c5df37d0a15239012d01a9aad1ceaec4de3ea237a10"
    ),
    "biglotto_official_prize_distributions.csv": (
        "7bf06dda59079ba8a963b405354967b2511f3665891214ddba2cdfa87c7b0329"
    ),
    "biglotto_strategy_universe.csv": (
        "f90c9773c3247eec63e1d51b7ead4a7e8e3227f0dfb689aa1533ee8e0c17cdbb"
    ),
    "biglotto_success_metrics.csv": (
        "b0a2aef7c2b92b98beb3126f06c3029ec479cc39e72d751b39495ac29d922d16"
    ),
    "biglotto_top10.csv": (
        "4924bfad34a0bda789151748cf336876f9247af7fb9c3f7d0d6bf41cb5fbcdac"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-61 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> str:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") != METHOD_ID:
            continue
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256") != SOURCE_SHA256
            or type(row.get("strategy_id")) is not str
        ):
            break
        return cast(str, row["strategy_id"])
    raise EvidenceBuildError("wave-61 catalog row changed")


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("native_ticket_case_count") != 4160
        or parity.get("status_counts")
        != {"CLOSED_REJECTED": 1963, "OK": 186}
        or parity.get("native_ticket_count_distribution")
        != {"15": 49, "25": 137}
        or parity.get("configuration_count_distribution")
        != {"3": 49, "5": 137}
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-61 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id: str,
) -> dict[str, object]:
    document, raw = _read_json(path)
    executions = cast(list[object], document.get("executions", []))
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(executions) != 2149
    ):
        raise EvidenceBuildError("wave-61 full input identity changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    portfolios: list[list[list[int]]] = []
    native_counts: Counter[int] = Counter()
    configuration_counts: Counter[int] = Counter()
    duplicate_counts: Counter[int] = Counter()
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-61 execution changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("wave-61 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reasons[cast(str, row.get("reason_code"))] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-61 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        tickets = cast(list[object], row.get("native_tickets", []))
        native_count = len(tickets)
        configuration_count = row.get("combination_count")
        if (
            native.get("legacy_method_id") != METHOD_ID
            or native.get("source_sha256") != SOURCE_SHA256
            or native.get("causal_protocol") != CAUSAL_PROTOCOL
            or native.get("candidate_k") is not None
            or row.get("candidate_k") != 49
            or native.get("combination_count") is not None
            or type(configuration_count) is not int
            or native.get("local_configuration_count")
            != configuration_count
            or native.get("native_ticket_count") != native_count
            or row.get("native_ticket_count") != native_count
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                "wave-61 native semantics changed"
            )
        typed_tickets = cast(list[list[int]], tickets)
        portfolios.append(typed_tickets)
        native_counts[native_count] += 1
        configuration_counts[configuration_count] += 1
        duplicate_counts[
            native_count
            - len({tuple(ticket) for ticket in typed_tickets})
        ] += 1
    if (
        statuses
        != {
            "CLOSED_EXECUTION_ERROR": 14,
            "CLOSED_REJECTED": 1949,
            "OK": 186,
        }
        or native_counts != {15: 49, 25: 137}
        or configuration_counts != {3: 49, 5: 137}
        or hashlib.sha256(_canonical_bytes(portfolios)).hexdigest()
        != EXPECTED_OK_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError(
            "wave-61 execution distribution changed"
        )
    return {
        "candidate_k_distribution": {"49": 186},
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_execution_count": 1963,
        "closed_reason_count": len(reasons),
        "combination_count_distribution": {
            str(key): value
            for key, value in sorted(configuration_counts.items())
        },
        "execution_status_counts": dict(sorted(statuses.items())),
        "legacy_method_id": METHOD_ID,
        "native_duplicate_ticket_count_distribution": {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        },
        "native_ticket_count_distribution": {
            str(key): value
            for key, value in sorted(native_counts.items())
        },
        "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
        "ok_execution_count": 186,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "ticket_sequence_sha256": EXPECTED_OK_SEQUENCE_SHA256,
    }


def _validate_report(
    *,
    report_file: Path,
    report_directory: Path,
) -> dict[str, str]:
    report, raw = _read_json(report_file)
    checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in report_directory.iterdir()
        if path.is_file()
    }
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_REPORT_FILE_SHA256
        or report.get("report_schema_version")
        != REPORT_SCHEMA_VERSION
        or report.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or report.get("report_sha256") != EXPECTED_REPORT_SHA256
        or report.get("catalog_sha256") != BASE_CATALOG_SHA256
        or report.get("dataset_sha256") != PINNED_DATASET_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("input_raw_sha256")
        != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or checksums != EXPECTED_REPORT_CHECKSUMS
    ):
        raise EvidenceBuildError("wave-61 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-61 artifact and return compact evidence."""

    strategy_id = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategy = _validate_input(
        input_file,
        strategy_id=strategy_id,
    )
    checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_FILE_SHA256,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "materialization_schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "parity": parity,
        "report_checksums": checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE61_PROTOCOL,
        "strategies": [strategy],
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--parity-file", required=True, type=Path)
    parser.add_argument("--report-file", required=True, type=Path)
    parser.add_argument("--report-directory", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        base_catalog_path=args.base_catalog,
        input_file=args.input_file,
        parity_file=args.parity_file,
        report_file=args.report_file,
        report_directory=args.report_directory,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
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
