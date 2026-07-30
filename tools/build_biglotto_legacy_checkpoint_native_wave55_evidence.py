#!/usr/bin/env python3
"""Build compact evidence for the wave-55 checkpoint-native backtests."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    BACKTEST_POLICY_VERSION,
    REPORT_SCHEMA_VERSION,
    RESEARCH_DISCLAIMER,
)
from lottolab.application.legacy_checkpoint_native_portfolios_wave55 import (
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_BY_SOURCE_NATIVE_WAVE55_METHOD,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_TIME,
    FROZEN_SOURCE_COMMIT,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE55_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE55_METHOD,
    MODEL_CANDIDATE_K,
    MODEL_CONTEXT_DRAW_COUNT,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE55_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE55_METHOD,
    RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SOURCE_NATIVE_WAVE55_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_checkpoint_native_batch_import_wave55 import (
    MATERIALIZATION_SCHEMA_VERSION,
    NONCAUSAL_TARGET_REASON,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE55_EVIDENCE_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE55_PARITY_V1"
)
BASE_CATALOG_SHA256 = (
    "6599e096044c967623bdf7d58f4fbe0e11515459bd77613cb389754ae72a58a1"
)
BASE_CATALOG_FILE_SHA256 = (
    "023434b64df1af74cde40191474133709eff35401273fe0f29d17b70009642f5"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 121,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 24,
}
EXPECTED_PROGRESS = {
    "backtested_count": 123,
    "closed_count": 65,
    "duplicate_alias_count": 11,
    "owner_decision_required_count": 22,
    "reproduced_count": 123,
    "total_strategy_count": 221,
    "uncompleted_count": 22,
}
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_FILE_SHA256 = (
    "e2b059af420c9988ff0eec057a77fdc372bb0277c48cb1d889e41a9ee7d4f53a"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "15257ad42fdb6fb8a7aa4e095e62f01c9575c1a448909827918858060c79f1d8"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "4b78a788b720f2f166d7cfbe3c95eae1f6193b0fcaf46158cb210f021e644371"
)
EXPECTED_PARITY_SHA256 = (
    "a76ed536c74aef55b096b60a2d8dd9b476b242ae39cf440a0f478aa9b116bc11"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "de04454b16afacb11d3ebbc79094c7e364b8cc3c7538f1aa77ff2aceb2c852a9"
)
EXPECTED_REPORT_SHA256 = (
    "63fe6c56873b2d14a92c8a92c13e5d5e6e69fcdb3061e6f7a3286a2942ba1993"
)
EXPECTED_TICKET_SEQUENCE_SHA256 = {
    "tools/predict_6expert.py": (
        "30f4d85081f05d0ff97b66c5841893a541d86291b8d4ad58e4ba7b00abcf7694"
    ),
    "tools/predict_next_draw.py": (
        "8910d2a6f3b95b1d0c637cedc95ad8df67dc70bca8f3292e45d3154de62ad2d9"
    ),
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "719ef8debb766edbd3d1366d70db1365b3e0fea616fbb79774142b73236932dd"
    ),
    "biglotto_execution_audit.csv": (
        "f0f411c670dd7dc1f963f97a0971c938ca475ba59829a6f7551f39603c00553c"
    ),
    "biglotto_full_rankings.csv": (
        "18a68a93f55f3f3bd3502ca7539fde4a5c8b902cb97b5990a34e7c67a5dbb0d8"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "de04454b16afacb11d3ebbc79094c7e364b8cc3c7538f1aa77ff2aceb2c852a9"
    ),
    "biglotto_official_prize_distributions.csv": (
        "04ec7ad7c8357abaa30e754881eed27cc819d23e659cff3bec7ec86b044dce47"
    ),
    "biglotto_strategy_universe.csv": (
        "a062ee2f021f56ed5102428aeb81f2f533d50c316b06a633f655c1a37a37bc4d"
    ),
    "biglotto_success_metrics.csv": (
        "1c117d0345be37661a2794dfecbe5ff5c3433af561e73f168087928f25e1d00a"
    ),
    "biglotto_top10.csv": (
        "cf0a3244e496e20a9812b604d1e94f797b344c0dacc82ca98ff6e4ec68547d18"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-55 evidence inputs violate the frozen contract."""


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


def _validate_catalog(path: Path) -> dict[str, str]:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    records = cast(list[object], catalog.get("records", []))
    by_method: dict[str, str] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            continue
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if method_id not in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
            continue
        if (
            row.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or row.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD[
                cast(str, method_id)
            ]
            or type(row.get("strategy_id")) is not str
        ):
            raise EvidenceBuildError(
                f"wave-55 catalog row changed: {method_id}"
            )
        by_method[cast(str, method_id)] = cast(str, row["strategy_id"])
    if set(by_method) != set(SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS):
        raise EvidenceBuildError("wave-55 catalog method set changed")
    return by_method


def _validate_parity(path: Path) -> dict[str, Any]:
    parity, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or parity.get("parity_schema_version")
        != PARITY_SCHEMA_VERSION
        or parity.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or parity.get("status") != "PASS"
        or parity.get("eligible_target_count") != 48
        or parity.get("native_ticket_case_count") != 432
        or parity.get("cross_method_positional_subset_match_count") != 48
        or parity.get("exact_alias_candidates") != []
        or parity.get("cross_wave_exact_alias_candidates") != []
        or parity.get("ledger_file_sha256") != LEDGER_FILE_SHA256
        or parity.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or parity.get("ticket_sequence_sha256_by_method")
        != EXPECTED_TICKET_SEQUENCE_SHA256
        or parity.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
    ):
        raise EvidenceBuildError("wave-55 parity identity changed")
    return parity


def _validate_input(
    path: Path,
    *,
    strategy_id_by_method: dict[str, str],
) -> list[dict[str, object]]:
    document, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_INPUT_FILE_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256")
        != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
        or len(cast(list[object], document.get("executions", [])))
        != 4298
    ):
        raise EvidenceBuildError("wave-55 full input identity changed")
    method_by_strategy_id = {
        strategy_id: method_id
        for method_id, strategy_id in strategy_id_by_method.items()
    }
    statuses: defaultdict[str, Counter[str]] = defaultdict(Counter)
    reasons: defaultdict[str, Counter[str]] = defaultdict(Counter)
    portfolios: defaultdict[str, list[list[list[int]]]] = defaultdict(list)
    strategies: dict[str, dict[str, object]] = {}
    for candidate in cast(
        list[object],
        document.get("executions", []),
    ):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("wave-55 execution changed")
        row = cast(dict[str, Any], candidate)
        strategy_id = row.get("strategy_id")
        method_id = method_by_strategy_id.get(cast(str, strategy_id))
        if method_id is None:
            raise EvidenceBuildError("wave-55 strategy identity changed")
        status = cast(str, row.get("status"))
        statuses[method_id][status] += 1
        if status != "OK":
            reason = row.get("reason_code")
            if reason != NONCAUSAL_TARGET_REASON:
                raise EvidenceBuildError(
                    "wave-55 closed reason changed"
                )
            reasons[method_id][cast(str, reason)] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError(
                "wave-55 native generation changed"
            )
        native = cast(dict[str, Any], native_raw)
        native_tickets = cast(
            list[object],
            row.get("native_tickets", []),
        )
        if (
            native.get("legacy_method_id") != method_id
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or native.get("candidate_k") is not None
            or native.get("source_candidate_k_values")
            != list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            )
            or row.get("candidate_k") != MODEL_CANDIDATE_K
            or native.get("combination_count") is not None
            or row.get("combination_count") is not None
            or native.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or row.get("native_ticket_count")
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or native.get("native_duplicate_ticket_count") != 0
            or native.get("model_context_draw_count")
            != MODEL_CONTEXT_DRAW_COUNT
            or native.get("checkpoint_introduction_commit")
            != CHECKPOINT_INTRODUCTION_COMMIT
            or native.get("checkpoint_introduction_time")
            != CHECKPOINT_INTRODUCTION_TIME
            or native.get("causal_eligibility_rule")
            != CAUSAL_ELIGIBILITY_RULE
            or native.get("source_reference_runtime")
            != SOURCE_REFERENCE_RUNTIME
            or native.get("random_protocol")
            != RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
            or native.get("randomness_used")
            is not RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or native.get("ledger_file_sha256")
            != LEDGER_FILE_SHA256
            or native.get("ledger_content_sha256")
            != LEDGER_CONTENT_SHA256
            or native.get("local_source_configuration")
            != LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or native.get("imported_comparators_excluded")
            != list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            )
            or len(native_tickets)
            != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError(
                f"wave-55 native semantics changed: {method_id}"
            )
        if any(not isinstance(ticket, list) for ticket in native_tickets):
            raise EvidenceBuildError("wave-55 native ticket changed")
        portfolios[method_id].append(
            cast(list[list[int]], native_tickets)
        )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
        sequence_sha256 = hashlib.sha256(
            _canonical_bytes(portfolios[method_id])
        ).hexdigest()
        if (
            statuses[method_id]
            != {"CLOSED_REJECTED": 2101, "OK": 48}
            or reasons[method_id]
            != {NONCAUSAL_TARGET_REASON: 2101}
            or len(portfolios[method_id]) != 48
            or sequence_sha256
            != EXPECTED_TICKET_SEQUENCE_SHA256[method_id]
        ):
            raise EvidenceBuildError(
                f"wave-55 execution distribution changed: {method_id}"
            )
        checkpoint_path, checkpoint_sha256, checkpoint_blob_id = (
            CHECKPOINT_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
        )
        strategies[method_id] = {
            "candidate_k_distribution": {"49": 48},
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "checkpoint_blob_id": checkpoint_blob_id,
            "checkpoint_path": checkpoint_path,
            "checkpoint_sha256": checkpoint_sha256,
            "closed_execution_count": 2101,
            "closed_reason_code_distribution": {
                NONCAUSAL_TARGET_REASON: 2101
            },
            "combination_count_distribution": {"null": 48},
            "execution_status_counts": {
                "CLOSED_REJECTED": 2101,
                "OK": 48,
            },
            "imported_comparators_excluded": list(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ),
            "legacy_method_id": method_id,
            "local_source_configuration": (
                LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ),
            "model_context_draw_count": MODEL_CONTEXT_DRAW_COUNT,
            "native_duplicate_ticket_count_distribution": {"0": 48},
            "native_ticket_count_distribution": {
                str(
                    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                        method_id
                    ]
                ): 48
            },
            "native_ticket_semantics": (
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ),
            "ok_execution_count": 48,
            "random_protocol": (
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
            ),
            "randomness_reproduction": (
                "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
            ),
            "randomness_used": (
                RANDOMNESS_USED_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
            ),
            "source_candidate_k_values": list(
                SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ),
            "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
            "source_sha256": (
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
            ),
            "ticket_sequence_sha256": sequence_sha256,
        }
    return [strategies[method_id] for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS]


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
        or report.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or report.get("target_draw_count") != 2149
        or report.get("progress") != EXPECTED_PROGRESS
        or report.get("input_raw_sha256")
        != EXPECTED_INPUT_FILE_SHA256
        or report.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or report.get("research_disclaimer") != RESEARCH_DISCLAIMER
        or checksums != EXPECTED_REPORT_CHECKSUMS
    ):
        raise EvidenceBuildError("wave-55 report identity changed")
    return checksums


def build_evidence(
    *,
    base_catalog_path: Path,
    input_file: Path,
    parity_file: Path,
    report_file: Path,
    report_directory: Path,
) -> dict[str, object]:
    """Validate all wave-55 artifacts and return compact evidence."""

    strategy_id_by_method = _validate_catalog(base_catalog_path)
    parity = _validate_parity(parity_file)
    strategies = _validate_input(
        input_file,
        strategy_id_by_method=strategy_id_by_method,
    )
    report_checksums = _validate_report(
        report_file=report_file,
        report_directory=report_directory,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "checkpoint_introduction_commit": (
            CHECKPOINT_INTRODUCTION_COMMIT
        ),
        "checkpoint_introduction_time": CHECKPOINT_INTRODUCTION_TIME,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
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
        "report_checksums": report_checksums,
        "report_file_sha256": EXPECTED_REPORT_FILE_SHA256,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "research_disclaimer": RESEARCH_DISCLAIMER,
        "source_native_protocol": SOURCE_NATIVE_WAVE55_PROTOCOL,
        "strategies": strategies,
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
                "strategy_count": len(
                    cast(list[object], document["strategies"])
                ),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
