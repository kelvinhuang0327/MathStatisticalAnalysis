#!/usr/bin/env python3
"""Build compact evidence for the wave-41 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave41 import (
    FROZEN_NETWORKX_SEMANTICS,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    GRAPH_METHOD_ID,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE41_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE41_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave41 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE41_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "ed095e2bd580075b42f6be5239bbb2bbf7cf7552e551aee96b9ab8a7c7dba88f"
)
BASE_CATALOG_FILE_SHA256 = (
    "a1041e8fac30b9680a3b36adbf4a0b65063e2e3c7ea8482eb1bb7f08283dc332"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "fbc8710f9771b755781f30fca3907cfe19995dc89b80d3874d689cac8064b1b3"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "f7c870cd7ac52980f728afa6a38d554db5eca2fc5f68685f3effd860f7eb412e"
)
EXPECTED_PARITY_FILE_SHA256 = (
    "d5585ed5acaa4807528c10a34668bcc423c34b7b20334d3a631626b8062127d7"
)
EXPECTED_PARITY_SHA256 = (
    "bbe310f97a66eb4f2b7163e14f2ef373721a4cd807f277f628b0744a79e11863"
)
EXPECTED_REPORT_SHA256 = (
    "460d3514f0a5928787e0f14ae7fc353dc18ac35e7e99a93300ec254e2e56d055"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "a5d842fd81c3b682c71417ebb5f9aa2b17609965dfd2e63ef822bb91c224e8f1"
)
EXPECTED_GRAPH_EDGE_SEQUENCE_SHA256 = (
    "51bb935dd96d992abf0e58b704d1ca35e79847806d78a903ce4f210270c392c6"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 79,
    "CLOSED_UNEXECUTABLE": 64,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 73,
}
EXPECTED_PROGRESS = {
    "backtested_count": 80,
    "closed_count": 64,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 72,
    "reproduced_count": 80,
    "total_strategy_count": 221,
    "uncompleted_count": 72,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "1be050716eadd123f5ba5841b2f70ef01db015e8edaeb1f726c65aa9ee118b94"
    ),
    "biglotto_execution_audit.csv": (
        "87a24c08a88a562d226c36ff962e1982ec1831c099673ff8952f80a27997fa1b"
    ),
    "biglotto_full_rankings.csv": (
        "c1a0a34e2660d14d727c0bf364b71811b954376a46e8e8c31899e913d73dfa43"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "a5d842fd81c3b682c71417ebb5f9aa2b17609965dfd2e63ef822bb91c224e8f1"
    ),
    "biglotto_official_prize_distributions.csv": (
        "8e627a1de6071161fb907ae4984df608cac348bde668a740fd5e9bd8261f8548"
    ),
    "biglotto_strategy_universe.csv": (
        "7cdd1278444f452a660643da1e61d970dd3d0f30fb1a25304f06a3d92da78f4a"
    ),
    "biglotto_success_metrics.csv": (
        "bcc537702ab9aad26e5418f9012df767899ef61d897e39d538cc27e46e773be1"
    ),
    "biglotto_top10.csv": (
        "1cffbf2586390e9fac2892c3c88b05f5a557dc079920a09bb5f28cd61318a28d"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-41 evidence inputs violate the frozen contract."""


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
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError(f"{path.name}: invalid JSON") from exc
    if not isinstance(document, dict):
        raise EvidenceBuildError(
            f"{path.name}: top level must be an object"
        )
    return cast(dict[str, Any], document), raw


def _validate_catalog(path: Path) -> str:
    catalog, raw = _read_json(path)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
    ):
        raise EvidenceBuildError("base catalog identity changed")
    matches: list[dict[str, Any]] = []
    for candidate in cast(list[object], catalog.get("records", [])):
        if not isinstance(candidate, dict):
            continue
        typed_candidate = cast(dict[str, Any], candidate)
        if typed_candidate.get("legacy_method_id") == GRAPH_METHOD_ID:
            matches.append(typed_candidate)
    if len(matches) != 1:
        raise EvidenceBuildError("wave-41 catalog row changed")
    row = matches[0]
    if (
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[GRAPH_METHOD_ID]
        or not isinstance(row.get("strategy_id"), str)
    ):
        raise EvidenceBuildError("wave-41 catalog identity changed")
    return cast(str, row["strategy_id"])


def _validate_input(
    document: dict[str, Any],
    raw: bytes,
    *,
    strategy_id: str,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_INPUT_SHA256
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("dataset_version")
        != MATERIALIZATION_SCHEMA_VERSION
        or len(cast(list[object], document.get("targets", []))) != 2149
    ):
        raise EvidenceBuildError("full input identity changed")
    executions = cast(list[object], document.get("executions", []))
    if len(executions) != 2149:
        raise EvidenceBuildError("full input execution count changed")
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    native_counts: Counter[int] = Counter()
    duplicates: Counter[int] = Counter()
    edge_counts: list[int] = []
    ok_count = 0
    for candidate in executions:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("full input execution is invalid")
        row = cast(dict[str, Any], candidate)
        if row.get("strategy_id") != strategy_id:
            raise EvidenceBuildError("execution strategy changed")
        status = cast(str, row.get("status"))
        statuses[status] += 1
        if status != "OK":
            reason = row.get("reason_code")
            if not isinstance(reason, str):
                raise EvidenceBuildError("closed reason changed")
            reasons[reason] += 1
            continue
        native_raw = row.get("native_generation")
        if not isinstance(native_raw, dict):
            raise EvidenceBuildError("native execution evidence changed")
        native = cast(dict[str, Any], native_raw)
        native_count = row.get("native_ticket_count")
        duplicate_count = native.get("native_duplicate_ticket_count")
        edge_count = native.get("graph_edge_count")
        if (
            native.get("legacy_method_id") != GRAPH_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or row.get("candidate_k") is not None
            or native.get("combination_count") is not None
            or row.get("combination_count") != 2
            or native.get("source_method_combination_count") != 2
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    GRAPH_METHOD_ID
                ]
            )
            or native.get("frozen_networkx_semantics")
            != FROZEN_NETWORKX_SEMANTICS
            or native.get("graph_node_count") != 49
            or native.get("random_protocol") != "NONE_DETERMINISTIC"
            or native.get("randomness_used") is not False
            or native.get("randomness_reproduction")
            != "SOURCE_DETERMINISTIC"
            or native.get("native_ticket_order")
            != "GRAPH_CENTRALITY_THEN_DEVIATION_BASELINE_SOURCE_ORDER"
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    GRAPH_METHOD_ID
                ]
            ]
            or type(native_count) is not int
            or native_count != 2
            or type(duplicate_count) is not int
            or type(edge_count) is not int
            or not 156 <= edge_count <= 942
            or len(cast(list[object], native.get("graph_ranked_numbers", [])))
            != 49
            or len(cast(list[object], row.get("native_tickets", []))) != 2
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
        ):
            raise EvidenceBuildError("native execution semantics changed")
        native_counts[native_count] += 1
        duplicates[duplicate_count] += 1
        edge_counts.append(edge_count)
        ok_count += 1
    edge_digest = hashlib.sha256(
        json.dumps(edge_counts, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        statuses
        != {"CLOSED_INSUFFICIENT_HISTORY": 50, "OK": 2099}
        or reasons
        != {"AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 50}
        or native_counts != {2: 2099}
        or duplicates != {0: 2099}
        or edge_digest != EXPECTED_GRAPH_EDGE_SEQUENCE_SHA256
    ):
        raise EvidenceBuildError("wave-41 execution distribution changed")
    return {
        "candidate_k_distribution": {"null": ok_count},
        "closed_execution_count": 50,
        "closed_reason_code_distribution": dict(sorted(reasons.items())),
        "execution_status_counts": dict(sorted(statuses.items())),
        "frozen_networkx_semantics": FROZEN_NETWORKX_SEMANTICS,
        "graph_edge_count_maximum": max(edge_counts),
        "graph_edge_count_minimum": min(edge_counts),
        "graph_edge_count_sequence_sha256": edge_digest,
        "legacy_method_id": GRAPH_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": {
            str(key): value for key, value in sorted(duplicates.items())
        },
        "native_ticket_count_distribution": {
            str(key): value for key, value in sorted(native_counts.items())
        },
        "native_ticket_count_upper_bound": (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "ok_execution_count": ok_count,
        "random_protocol": "NONE_DETERMINISTIC_NATIVE_SELECTION",
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "source_history_order_detail": (
            SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "source_method_combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "source_method_combination_members": list(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                GRAPH_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[GRAPH_METHOD_ID]
        ),
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest()
        != EXPECTED_PARITY_FILE_SHA256
        or document.get("parity_sha256") != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 65
        or document.get("networkx_reference_version") != "3.2.1"
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 4
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
        "networkx_reference_version": document[
            "networkx_reference_version"
        ],
        "parity_file_sha256": EXPECTED_PARITY_FILE_SHA256,
        "parity_sha256": document["parity_sha256"],
        "source_artifacts": document["source_artifacts"],
        "status": document["status"],
        "support_artifacts": document["support_artifacts"],
    }


def _validate_report(
    document: dict[str, Any],
    raw: bytes,
    *,
    report_directory: Path,
) -> None:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_REPORT_FILE_SHA256
        or document.get("report_sha256") != EXPECTED_REPORT_SHA256
        or document.get("report_schema_version") != REPORT_SCHEMA_VERSION
        or document.get("backtest_policy_version")
        != BACKTEST_POLICY_VERSION
        or document.get("input_raw_sha256") != EXPECTED_INPUT_SHA256
        or document.get("input_canonical_sha256")
        != EXPECTED_INPUT_CANONICAL_SHA256
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or document.get("target_draw_count") != 2149
        or document.get("progress") != EXPECTED_PROGRESS
    ):
        raise EvidenceBuildError("pre-overlay report identity changed")
    actual_checksums = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in report_directory.iterdir()
        if path.is_file()
    }
    if actual_checksums != EXPECTED_REPORT_CHECKSUMS:
        raise EvidenceBuildError("pre-overlay report checksums changed")


def build_wave41_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-41 evidence."""

    strategy_id = _validate_catalog(catalog_path)
    input_document, input_raw = _read_json(input_path)
    strategy = _validate_input(
        input_document,
        input_raw,
        strategy_id=strategy_id,
    )
    parity_document, parity_raw = _read_json(parity_path)
    parity = _validate_parity(parity_document, parity_raw)
    report_document, report_raw = _read_json(report_path)
    _validate_report(
        report_document,
        report_raw,
        report_directory=report_path.parent,
    )
    return {
        "backtest_policy_version": BACKTEST_POLICY_VERSION,
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "constructor": CONSTRUCTOR_IDENTIFIER,
        "dataset_sha256": EXPECTED_DATABASE_SHA256,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "input_canonical_sha256": EXPECTED_INPUT_CANONICAL_SHA256,
        "input_raw_sha256": EXPECTED_INPUT_SHA256,
        "materialization_schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "parity": parity,
        "report_checksums": EXPECTED_REPORT_CHECKSUMS,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_sha256": EXPECTED_REPORT_SHA256,
        "strategies": [strategy],
        "target_draw_count": 2149,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--parity", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_wave41_evidence(
        catalog_path=args.catalog,
        input_path=args.input,
        parity_path=args.parity,
        report_path=args.report,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
                "strategy_count": 1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
