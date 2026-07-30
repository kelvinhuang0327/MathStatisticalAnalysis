#!/usr/bin/env python3
"""Build compact evidence for the wave-63 advanced-method causal replay."""

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
from lottolab.application.legacy_advanced_methods_native_portfolios_wave63 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    FROZEN_SOURCE_COMMIT,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    METHOD_ORDER,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    RANDOM_PROTOCOL,
    SOURCE_NATIVE_WAVE63_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_advanced_methods_native_batch_import_wave63 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_ADVANCED_METHODS_WAVE63_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_ADVANCED_METHODS_WAVE63_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "093eca2714e5f3c35e0b03eaf359cca4c8570c7d4b2f0a092b06eacfc3629063"
)
BASE_CATALOG_FILE_SHA256 = (
    "0e8a8ab19084a112a354b754d98fe91386d2fafa4617db352fa8305af8f84ae4"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 132,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 3,
}
EXPECTED_PROGRESS = {
    "backtested_count": 133,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 2,
    "reproduced_count": 133,
    "total_strategy_count": 221,
    "uncompleted_count": 2,
}
EXPECTED_INPUT_FILE_SHA256 = (
    "e501c2e1b0a5c610bae3822a2784a72860e2c549daadb37c344de61d16129493"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "155766ddc1f7581392d91fc8f5e79a433f6e245a9feefb5cb059b8d2594af7c9"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "52dc9ee26bde75e8fab2045ae1aa4aaa05f80dbd2dd967fb5cbf2c7958af9d6d"
)
EXPECTED_PARITY_SHA256 = (
    "644f9b6cd3ddb19b647056da2d2cccc7c9e0119f8567df7c22a3ce67f8d46169"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "7bb01b29c4e30b12c7feadbb6253c1b99986c0ec6fc66430399276088f0c702b"
)
EXPECTED_REPORT_SHA256 = (
    "8fb4ab606e88cf9c1dc74f8ceaf6a476e76aa978925ed85ceb8e8b16a9df45c7"
)
EXPECTED_ALL_SEQUENCE_SHA256 = (
    "7a1927a300c96155ce9914344fa0247911ea2c3f0dda55ec84192766a2b6ed5f"
)
EXPECTED_OK_SEQUENCE_SHA256 = (
    "9562b26912310b56610b3c3aa1da426beb06dd7493123caf0a42d6dc479020a2"
)
EXPECTED_ORDERED20_SEQUENCE_SHA256 = (
    "82b0d0465a493c9a99f1b0fb4bc95cf4dcd3e13de16f748b9879e45878ee44ba"
)
EXPECTED_EXECUTION_COUNTS = {
    "CLOSED_INSUFFICIENT_HISTORY": 1,
    "OK": 2148,
}
EXPECTED_CLOSED_REASONS = {
    "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF": 1,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "20": 2133,
    "21": 8,
    "22": 6,
    "23": 1,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "4ec17053e9b2a46b52ab43c09a9c08e94a563e066f88f0b8726c6c21eefdbb6f"
    ),
    "biglotto_execution_audit.csv": (
        "703e958250b521de3c18cab994134f536c7835906983b2796765b466019cdb88"
    ),
    "biglotto_full_rankings.csv": (
        "a3a46f38e32db9c5ba050e3ac3e193761819fb5491c1d7aca60a2a8c63a98e58"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "7bb01b29c4e30b12c7feadbb6253c1b99986c0ec6fc66430399276088f0c702b"
    ),
    "biglotto_official_prize_distributions.csv": (
        "2386b18689b4fe6955392832dc28b169db8f6e9acd182b54023a03d87fc7c163"
    ),
    "biglotto_strategy_universe.csv": (
        "1f6377c57b8afcbb33a9bb9b0fa84922f502e764b2a4533231e4bef406d95edb"
    ),
    "biglotto_success_metrics.csv": (
        "775ee76083c3bc0923c82bed3b668b2cbdb15ceafaef56b27ef8c7b89f509ac4"
    ),
    "biglotto_top10.csv": (
        "6193ba6330d34228e1602edb0d8a4edf97cf1a421ca7523542ce26059065455f"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-63 evidence inputs violate the frozen contract."""


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
    raise EvidenceBuildError("wave-63 catalog row changed")


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("status_counts") != EXPECTED_EXECUTION_COUNTS
        or parity.get("native_ticket_case_count") != 53700
        or parity.get("native_ticket_count_distribution")
        != {"25": 2148}
        or parity.get("native_duplicate_ticket_count_distribution")
        != EXPECTED_DUPLICATE_DISTRIBUTION
        or parity.get("ticket_sequence_sha256")
        != EXPECTED_ALL_SEQUENCE_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-63 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id: str,
) -> dict[str, object]:
    document, raw = _read_json(path)
    executions = cast(list[object], document.get("executions", []))
    provenance = cast(
        dict[str, Any],
        document.get("source_provenance", {}),
    )
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", [])))
        != 2149
        or len(executions) != 2149
        or provenance.get("execution_status_counts")
        != EXPECTED_EXECUTION_COUNTS
        or provenance.get("native_ticket_count_distribution")
        != {"25": 2148}
        or provenance.get("combination_count_distribution")
        != {"10": 2148}
        or provenance.get(
            "native_duplicate_ticket_count_distribution"
        )
        != EXPECTED_DUPLICATE_DISTRIBUTION
    ):
        raise EvidenceBuildError("wave-63 full input identity changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    portfolios: list[list[list[int]]] = []
    ordered20: list[list[list[int]]] = []
    all_sequence: list[list[list[int]] | None] = []
    duplicate_counts: Counter[int] = Counter()
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-63 execution changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("wave-63 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = cast(str, row.get("reason_code"))
            reasons[reason] += 1
            all_sequence.append(None)
            if any(
                key in row
                for key in (
                    "native_tickets",
                    "ordered_portfolio",
                    "portfolio_ticket_count",
                )
            ):
                raise EvidenceBuildError(
                    "wave-63 closed row carries tickets"
                )
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-63 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        tickets = cast(list[list[int]], row.get("native_tickets", []))
        ordered = cast(
            list[list[int]],
            row.get("ordered_portfolio", []),
        )
        ledger_index = native.get("ledger_target_index")
        if (
            native.get("legacy_method_id") != METHOD_ID
            or native.get("source_sha256") != SOURCE_SHA256
            or native.get("causal_protocol") != CAUSAL_PROTOCOL
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values") != [49]
            or row.get("candidate_k") != 49
            or native.get("combination_count") is not None
            or native.get("local_configuration_count") != 10
            or row.get("combination_count") != 10
            or native.get("native_ticket_count") != 25
            or row.get("native_ticket_count") != 25
            or len(tickets) != 25
            or row.get("portfolio_ticket_count") != 20
            or len(ordered) != 20
            or native.get("local_method_order") != list(METHOD_ORDER)
            or native.get("native_ticket_count_semantics")
            != NATIVE_TICKET_SEMANTICS
            or native.get("native_ticket_order")
            != NATIVE_TICKET_ORDER
            or native.get("random_protocol") != RANDOM_PROTOCOL
            or native.get("source_random_baseline_excluded")
            is not True
            or native.get(
                "source_main_reverse_chronological_state_reuse_excluded"
            )
            is not True
            or native.get("target_stable_reinstantiation") is not True
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or type(ledger_index) is not int
            or ledger_index < 1
            or native.get("source_history_input_draw_count")
            != min(ledger_index, 1000)
        ):
            raise EvidenceBuildError(
                "wave-63 native semantics changed"
            )
        portfolios.append(tickets)
        ordered20.append(ordered)
        all_sequence.append(tickets)
        duplicate_counts[
            len(tickets) - len({tuple(ticket) for ticket in tickets})
        ] += 1
    if (
        dict(statuses) != EXPECTED_EXECUTION_COUNTS
        or dict(reasons) != EXPECTED_CLOSED_REASONS
        or {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        }
        != EXPECTED_DUPLICATE_DISTRIBUTION
        or hashlib.sha256(_canonical_bytes(all_sequence)).hexdigest()
        != EXPECTED_ALL_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(portfolios)).hexdigest()
        != EXPECTED_OK_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(ordered20)).hexdigest()
        != EXPECTED_ORDERED20_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError(
            "wave-63 execution distribution changed"
        )
    return {
        "candidate_k_distribution": {"49": 2148},
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_execution_count": 1,
        "closed_reason_code_distribution": (
            EXPECTED_CLOSED_REASONS
        ),
        "combination_count_distribution": {"10": 2148},
        "execution_status_counts": EXPECTED_EXECUTION_COUNTS,
        "legacy_method_id": METHOD_ID,
        "local_method_order": list(METHOD_ORDER),
        "native_duplicate_ticket_count_distribution": (
            EXPECTED_DUPLICATE_DISTRIBUTION
        ),
        "native_ticket_count_distribution": {"25": 2148},
        "native_ticket_order": NATIVE_TICKET_ORDER,
        "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
        "ok_execution_count": 2148,
        "ordered20_sequence_sha256": (
            EXPECTED_ORDERED20_SEQUENCE_SHA256
        ),
        "random_protocol": RANDOM_PROTOCOL,
        "randomness_reproduction": (
            "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
        ),
        "source_candidate_k_values": [49],
        "source_history_input_upper_bound": 1000,
        "source_main_reverse_chronological_state_reuse_excluded": True,
        "source_random_baseline_excluded": True,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "target_stable_reinstantiation": True,
        "ticket_sequence_sha256": EXPECTED_ALL_SEQUENCE_SHA256,
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
        raise EvidenceBuildError("wave-63 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    if (
        len(metrics) != 128
        or {row.get("prefix_count") for row in metrics}
        != {5, 10, 15, 20}
        or {row.get("window") for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({row.get("criterion") for row in metrics}) != 8
    ):
        raise EvidenceBuildError(
            "wave-63 report coverage changed"
        )
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate every wave-63 artifact and return compact evidence."""

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
        "materialization_schema_version": (
            MATERIALIZATION_SCHEMA_VERSION
        ),
        "parity": parity,
        "report_checksums": checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE63_PROTOCOL,
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
