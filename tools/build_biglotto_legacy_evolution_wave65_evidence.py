#!/usr/bin/env python3
"""Build compact evidence for the wave-65 frozen evolution-engine replay."""

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
    FIRST_EXECUTABLE_TARGET_INDEX,
    FROZEN_SOURCE_COMMIT,
    LEADERBOARD_SEQUENCE_SHA256,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE65_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_evolution_native_batch_import_wave65 import (
    HISTORY_INPUT_CANONICAL_SHA256,
    HISTORY_INPUT_FILE_SHA256,
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_EVOLUTION_WAVE65_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = "BIG_LOTTO_EVOLUTION_WAVE65_PARITY_V1"
BASE_CATALOG_SHA256 = (
    "f66487d501864ee00f62a7cb237175600308120f7ad60df79681e812ae7e34e9"
)
BASE_CATALOG_FILE_SHA256 = (
    "36f2a7cf61f5e0c9d436154f8477ebd320d287e8601debbc47409ab45b1e2eb1"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 134,
    "CLOSED_UNEXECUTABLE": 74,
    "DUPLICATE_ALIAS": 12,
    "OWNER_DECISION_REQUIRED": 1,
}
EXPECTED_PROGRESS = {
    "backtested_count": 135,
    "closed_count": 74,
    "duplicate_alias_count": 12,
    "owner_decision_required_count": 0,
    "reproduced_count": 135,
    "total_strategy_count": 221,
    "uncompleted_count": 0,
}
EXPECTED_INPUT_FILE_SHA256 = (
    "172fbf2ac4c3bbe7c7e6da11089067f68f10d6c5d6f5008983609c49f4fcbe71"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "8d147879497fcf78134e42801203a9499dfc11fc23c1f4de658a0c74c7128d1b"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "97b68328d7a6435f18cadc3785b5f1d96abdf37044c2b24581fdf01b784a3195"
)
EXPECTED_PARITY_SHA256 = (
    "bd573643a061f27a9620fb296bca2679dabcd610a9c162bed8c38ca2c7afe0da"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "98bbf9a02c2b0621576c3824d52c116c0071b81fce7f4db9987dcd38e234dab4"
)
EXPECTED_REPORT_SHA256 = (
    "26f5a59b060aec251a3882ce31f8ee9c77ecb324e868013e425cb0f94dfe7a08"
)
EXPECTED_OK_SEQUENCE_SHA256 = (
    "0e56f17f6f108ab1950cc7a1b9907b5d16a18f3f0b7857d357f8001e367f64af"
)
EXPECTED_ORDERED20_SEQUENCE_SHA256 = (
    "7b4105380f8584dff44650fc2b2460ab207ad3e6a91b90150c76c728f74212d2"
)
EXPECTED_OK_ORDERED20_SEQUENCE_SHA256 = (
    "9643972fda5c60083b55dcb1f366d19867a9f77cd59db2c5bf9bcc91452c0ff3"
)
EXPECTED_EXECUTION_COUNTS = {
    "CLOSED_INSUFFICIENT_HISTORY": 501,
    "OK": 1648,
}
EXPECTED_CLOSED_REASONS = {CLOSED_REASON: 501}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "b7be03239ce84936f951b79c43276b950e37d5811845a0c6f849d3736969fb76"
    ),
    "biglotto_execution_audit.csv": (
        "910e89022b0df4dcc260f900b79af0b458197d3446edba55941a425eba41701e"
    ),
    "biglotto_full_rankings.csv": (
        "faa3522add3d12ca197a091255f39a47c70b776a2e3458fc87f02d1f21aa2b27"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        EXPECTED_REPORT_FILE_SHA256
    ),
    "biglotto_official_prize_distributions.csv": (
        "d720ed8a10cc9befbbc3ad3371d294e53e655ad93b1acc1e083b13c9be798bfe"
    ),
    "biglotto_strategy_universe.csv": (
        "87d25d280baf1f31ced2ae3f95864d46f57d8ef8a640e9cdf0b8095ac71b92a6"
    ),
    "biglotto_success_metrics.csv": (
        "43bc146590996fce6ca18885f3ad21c7f3a6f619a7066f6902f613725adf8de2"
    ),
    "biglotto_top10.csv": (
        "91d42b45d9ac1de133bef20450159b530080c4ab07d11f79a4221d6e01b11656"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-65 evidence inputs violate the frozen contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceBuildError(
            f"{path.name}: must be a regular non-symlink file"
        )
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
    raise EvidenceBuildError("wave-65 catalog row changed")


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    reference = cast(
        dict[str, object],
        parity.get("reference_equivalence", {}),
    )
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("status_counts") != EXPECTED_EXECUTION_COUNTS
        or parity.get("target_count") != 2149
        or parity.get("native_ticket_position_count") != 12959
        or parity.get("native_ticket_count_distribution")
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or parity.get("native_duplicate_ticket_count_distribution")
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or parity.get("ticket_sequence_sha256")
        != TICKET_SEQUENCE_SHA256
        or parity.get("leaderboard_sequence_sha256")
        != LEADERBOARD_SEQUENCE_SHA256
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or reference.get("status") != "PASS"
        or reference.get("cutoff_501_native_projection_sha256")
        != reference.get("cutoff_501_memoized_projection_sha256")
        or len(cast(list[object], parity.get("shards", []))) != 83
    ):
        raise EvidenceBuildError("wave-65 parity identity changed")
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
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or provenance.get(
            "native_duplicate_ticket_count_distribution"
        )
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or provenance.get("native_ticket_position_count") != 12959
        or provenance.get("history_input_file_sha256")
        != HISTORY_INPUT_FILE_SHA256
        or provenance.get("history_input_canonical_sha256")
        != HISTORY_INPUT_CANONICAL_SHA256
        or provenance.get("candidate_k") is not None
        or provenance.get("combination_count") is not None
    ):
        raise EvidenceBuildError("wave-65 full input identity changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    ticket_counts: Counter[int] = Counter()
    duplicate_counts: Counter[int] = Counter()
    all_native: list[list[list[int]] | None] = []
    ok_native: list[list[list[int]]] = []
    all_ordered: list[list[list[int]] | None] = []
    ok_ordered: list[list[list[int]]] = []
    for target_index, candidate in enumerate(executions):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-65 execution changed")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("wave-65 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = cast(str, row.get("reason_code"))
            reasons[reason] += 1
            all_native.append(None)
            all_ordered.append(None)
            if any(
                key in row
                for key in (
                    "native_tickets",
                    "ordered_portfolio",
                    "portfolio_ticket_count",
                    "candidate_k",
                    "combination_count",
                )
            ):
                raise EvidenceBuildError(
                    "wave-65 closed row carries ticket semantics"
                )
            if target_index == 0:
                if any(
                    key in row
                    for key in (
                        "history_cutoff_draw_number",
                        "history_cutoff_draw_date",
                    )
                ):
                    raise EvidenceBuildError(
                        "wave-65 first target has a causal predecessor"
                    )
            elif (
                type(row.get("history_cutoff_draw_number")) is not str
                or type(row.get("history_cutoff_draw_date")) is not str
            ):
                raise EvidenceBuildError(
                    "wave-65 closed prefix cutoff changed"
                )
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-65 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        tickets = cast(list[list[int]], row.get("native_tickets", []))
        ordered = cast(
            list[list[int]],
            row.get("ordered_portfolio", []),
        )
        native_count = len(tickets)
        duplicate_count = native_count - len(
            {tuple(ticket) for ticket in tickets}
        )
        if (
            target_index < FIRST_EXECUTABLE_TARGET_INDEX
            or native.get("legacy_method_id") != METHOD_ID
            or native.get("source_sha256") != SOURCE_SHA256
            or native.get("causal_protocol") != CAUSAL_PROTOCOL
            or native.get("acceleration_protocol")
            != ACCELERATION_PROTOCOL
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values") != []
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count") is not None
            or native.get("native_ticket_count") != native_count
            or row.get("native_ticket_count") != native_count
            or native.get("native_duplicate_ticket_count")
            != duplicate_count
            or row.get("portfolio_ticket_count") != 20
            or len(ordered) != 20
            or native.get("native_ticket_count_semantics")
            != NATIVE_TICKET_SEMANTICS
            or native.get("native_ticket_order")
            != NATIVE_TICKET_ORDER
            or native.get("determinism_protocol")
            != DETERMINISM_PROTOCOL
            or native.get("source_random_state_explicit") is not True
            or native.get("repeatability_parity_passed") is not True
            or native.get("driver_generations") != DRIVER_GENERATIONS
            or native.get("driver_population_size")
            != DRIVER_POPULATION_SIZE
            or native.get("driver_n_test") != DRIVER_N_TEST
            or native.get("engine_seed") != ENGINE_SEED
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("ledger_target_index") != target_index
            or native.get("source_history_input_draw_count")
            != target_index
            or len(cast(list[object], native.get("leaderboard", [])))
            != native_count
        ):
            raise EvidenceBuildError("wave-65 native semantics changed")
        ticket_counts[native_count] += 1
        duplicate_counts[duplicate_count] += 1
        ok_native.append(tickets)
        all_native.append(tickets)
        ok_ordered.append(ordered)
        all_ordered.append(ordered)
    if (
        dict(statuses) != EXPECTED_EXECUTION_COUNTS
        or dict(reasons) != EXPECTED_CLOSED_REASONS
        or {
            str(key): value
            for key, value in sorted(ticket_counts.items())
        }
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        }
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or hashlib.sha256(_canonical_bytes(all_native)).hexdigest()
        != TICKET_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(ok_native)).hexdigest()
        != EXPECTED_OK_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(all_ordered)).hexdigest()
        != EXPECTED_ORDERED20_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(ok_ordered)).hexdigest()
        != EXPECTED_OK_ORDERED20_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError("wave-65 execution distribution changed")
    return {
        "candidate_k_distribution": {"NONE": 1648},
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_execution_count": 501,
        "closed_reason_code_distribution": EXPECTED_CLOSED_REASONS,
        "combination_count_distribution": {"NONE": 1648},
        "determinism_protocol": DETERMINISM_PROTOCOL,
        "driver_generations": DRIVER_GENERATIONS,
        "driver_n_test": DRIVER_N_TEST,
        "driver_population_size": DRIVER_POPULATION_SIZE,
        "engine_seed": ENGINE_SEED,
        "execution_status_counts": EXPECTED_EXECUTION_COUNTS,
        "legacy_method_id": METHOD_ID,
        "native_duplicate_ticket_count_distribution": (
            EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        ),
        "native_ticket_count_distribution": (
            EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        ),
        "native_ticket_order": NATIVE_TICKET_ORDER,
        "native_ticket_position_count": 12959,
        "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
        "ok_execution_count": 1648,
        "ordered20_sequence_sha256": (
            EXPECTED_ORDERED20_SEQUENCE_SHA256
        ),
        "source_random_state_explicit": True,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "ticket_sequence_sha256": TICKET_SEQUENCE_SHA256,
    }


def _validate_report(
    *,
    report_file: Path,
    report_directory: Path,
    strategy_id: str,
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
        or len(cast(list[object], report.get("universe", []))) != 221
        or len(cast(list[object], report.get("rankings", []))) != 28288
        or len(cast(list[object], report.get("top_10", []))) != 128
        or len(
            cast(
                list[object],
                report.get("official_prize_distributions", []),
            )
        )
        != 16
    ):
        raise EvidenceBuildError("wave-65 report identity changed")
    metrics = cast(list[dict[str, Any]], report.get("metrics", []))
    if (
        len(metrics) != 128
        or {row.get("strategy_id") for row in metrics}
        != {strategy_id}
        or {row.get("prefix_count") for row in metrics}
        != {5, 10, 15, 20}
        or {row.get("window") for row in metrics}
        != {"FULL", "RECENT_750", "RECENT_300", "RECENT_50"}
        or len({row.get("criterion") for row in metrics}) != 8
        or not all(row.get("rankable") is True for row in metrics)
        or not all(
            isinstance(row.get("exact_random_baseline_probability"), dict)
            and isinstance(row.get("random_baseline_rate_difference"), dict)
            for row in metrics
        )
    ):
        raise EvidenceBuildError("wave-65 report coverage changed")
    rankings = cast(list[dict[str, Any]], report.get("rankings", []))
    if (
        sum(row.get("strategy_id") == strategy_id for row in rankings)
        != 128
        or any(
            row.get("strategy_id") != strategy_id
            and not row.get("unranked_reason")
            for row in rankings
        )
    ):
        raise EvidenceBuildError(
            "wave-65 complete-universe ranking changed"
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
    """Validate every wave-65 artifact and return compact evidence."""

    strategy_id = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategy = _validate_input(
        input_file,
        strategy_id=strategy_id,
    )
    checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
        strategy_id=strategy_id,
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
        "source_native_protocol": SOURCE_NATIVE_WAVE65_PROTOCOL,
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
    evidence = build_evidence(
        base_catalog_path=args.base_catalog,
        input_file=args.input_file,
        parity_file=args.parity_file,
        report_file=args.report_file,
        report_directory=args.report_directory,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
                "strategy_count": len(
                    cast(list[object], evidence["strategies"])
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
