#!/usr/bin/env python3
"""Build compact evidence for the wave-34 causal source-native batch."""

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
from lottolab.application.legacy_source_native_portfolios_wave34 import (
    AUTO_OPTIMIZER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE34_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE34_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE34_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE34_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD,
    VARIANT_CONFIGURATIONS,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave34 import (
    MATERIALIZATION_SCHEMA_VERSION,
)

EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE34_EVIDENCE_V1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "8d6a97dd1f2565da903d8ae86ff75503f0d97a748f6d96e9f9a36391801fd719"
)
BASE_CATALOG_FILE_SHA256 = (
    "a025d60b023b0bc641ee3410653d49296c1984b65eba90713ae0c928ec1810e7"
)
EXPECTED_DATABASE_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
EXPECTED_INPUT_SHA256 = (
    "7f0ac4e7289af91e70a420b386206f711dfc3e66e6e26a079263efeabb1427e9"
)
EXPECTED_INPUT_CANONICAL_SHA256 = (
    "c893cfea5294e3b778acd1bb3d70ea195af2d6730a3a87ea0d9b65442e1770bd"
)
EXPECTED_PARITY_SHA256 = (
    "36ec1118ac9783579d27de74f30fccec8d2ba2965c73b32bd8372ca69b61ee73"
)
EXPECTED_REPORT_SHA256 = (
    "09caddd3016be8617fe747c134ebf333e4bd1b91cb85ff0019bc690f4121ba46"
)
EXPECTED_REPORT_FILE_SHA256 = (
    "7b28193aac237e985632d472b3d4a3218039de4ae1da7ff4fb91b79f0600d9ca"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 77,
    "CLOSED_UNEXECUTABLE": 38,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 101,
}
EXPECTED_PROGRESS = {
    "backtested_count": 78,
    "closed_count": 38,
    "duplicate_alias_count": 5,
    "owner_decision_required_count": 100,
    "reproduced_count": 78,
    "total_strategy_count": 221,
    "uncompleted_count": 100,
}
EXPECTED_DUPLICATE_DISTRIBUTION = {
    "3": 130,
    "4": 333,
    "5": 451,
    "6": 405,
    "7": 338,
    "8": 179,
    "9": 77,
    "10": 27,
    "11": 21,
    "12": 30,
    "13": 34,
    "14": 18,
    "15": 21,
    "16": 19,
    "17": 7,
    "18": 7,
    "19": 1,
    "20": 22,
    "21": 18,
    "22": 9,
    "23": 1,
}
EXPECTED_REPORT_CHECKSUMS = {
    "SHA256SUMS": (
        "f67bd8cd91d4c12e7004f0595471c98c723e8f12939ac1271525f433fd53c0a3"
    ),
    "biglotto_execution_audit.csv": (
        "fad1d2db5d56bbaa41e6ee2b04ff3ad0335e6c5b6d59d626003af426b843effc"
    ),
    "biglotto_full_rankings.csv": (
        "5ad4cec1f049323a9d6a36e04d544894e4f6013ef0d3ce59fa7dd10f3ab18aee"
    ),
    "biglotto_multi_ticket_backtest_report.json": (
        "7b28193aac237e985632d472b3d4a3218039de4ae1da7ff4fb91b79f0600d9ca"
    ),
    "biglotto_official_prize_distributions.csv": (
        "e9481ecc0a42cd96a7f38c818accd74e83665331ce672eaaba599f5b1e442fe7"
    ),
    "biglotto_strategy_universe.csv": (
        "5062710b6bdf9747223b827eb5cab2873a91d67fae0a7d36d9ba8b380faaab84"
    ),
    "biglotto_success_metrics.csv": (
        "53162ec872ac8b6a00dcaf94ae539681ba165ba6c5b8e4dab1da5fbf934a6733"
    ),
    "biglotto_top10.csv": (
        "1f2e9c5bcf4f72461d9a58a7a3877da598f9ed0545cbc8bf568584ece8e4501b"
    ),
}


class EvidenceBuildError(ValueError):
    """Wave-34 evidence inputs violate the frozen contract."""


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
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == AUTO_OPTIMIZER_METHOD_ID:
            matches.append(row)
    if len(matches) != 1:
        raise EvidenceBuildError("wave-34 catalog row changed")
    row = matches[0]
    if (
        row.get("reproduction_status") != "OWNER_DECISION_REQUIRED"
        or row.get("source_sha256")
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
            AUTO_OPTIMIZER_METHOD_ID
        ]
        or not isinstance(row.get("strategy_id"), str)
    ):
        raise EvidenceBuildError("wave-34 catalog identity changed")
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
    duplicates: Counter[int] = Counter()
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
        history_count = native.get("history_draw_count")
        if type(history_count) is not int:
            raise EvidenceBuildError("history count changed")
        expected_history_counts = [
            min(history_count, window)
            for _method_name, window in VARIANT_CONFIGURATIONS
        ]
        if (
            native.get("legacy_method_id") != AUTO_OPTIMIZER_METHOD_ID
            or native.get("source_sha256")
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
            or native.get("source_history_order")
            != SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
            or native.get("source_history_order_detail")
            != SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
            or native.get("candidate_k") is not None
            or row.get("candidate_k") is not None
            or native.get("candidate_pools") != []
            or native.get("combination_count") is not None
            or row.get("combination_count") != 25
            or native.get("combination_members")
            != list(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    AUTO_OPTIMIZER_METHOD_ID
                ]
            )
            or native.get("variant_history_draw_counts")
            != expected_history_counts
            or native.get("native_ticket_count") != 25
            or row.get("native_ticket_count") != 25
            or len(cast(list[object], row.get("native_tickets", [])))
            != 25
            or len(cast(list[object], row.get("ordered_portfolio", [])))
            != 20
            or native.get("frozen_support_artifacts")
            != [
                list(item)
                for item in FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD[
                    AUTO_OPTIMIZER_METHOD_ID
                ]
            ]
        ):
            raise EvidenceBuildError("native execution semantics changed")
        duplicate_count = native.get("native_duplicate_ticket_count")
        if type(duplicate_count) is not int:
            raise EvidenceBuildError("native duplicate count changed")
        duplicates[duplicate_count] += 1
        ok_count += 1
    duplicate_distribution = {
        str(key): value for key, value in sorted(duplicates.items())
    }
    if (
        statuses != {"CLOSED_INSUFFICIENT_HISTORY": 1, "OK": 2148}
        or reasons
        != {"AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM": 1}
        or duplicate_distribution != EXPECTED_DUPLICATE_DISTRIBUTION
    ):
        raise EvidenceBuildError("wave-34 execution distribution changed")
    return {
        "candidate_k_distribution": {"null": ok_count},
        "closed_execution_count": 1,
        "closed_reason_code_distribution": dict(sorted(reasons.items())),
        "execution_status_counts": dict(sorted(statuses.items())),
        "legacy_method_id": AUTO_OPTIMIZER_METHOD_ID,
        "minimum_history_draws": (
            MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "native_duplicate_ticket_count_distribution": (
            duplicate_distribution
        ),
        "native_ticket_count": (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "native_ticket_semantics": (
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "ok_execution_count": ok_count,
        "random_protocol": "NONE_DETERMINISTIC",
        "source_history_order": (
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "source_history_order_detail": (
            SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "source_method_combination_count": (
            SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
        "source_sha256": (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
                AUTO_OPTIMIZER_METHOD_ID
            ]
        ),
    }


def _validate_parity(
    document: dict[str, Any],
    raw: bytes,
) -> dict[str, object]:
    if (
        hashlib.sha256(raw).hexdigest() != EXPECTED_PARITY_SHA256
        or document.get("status") != "PASS"
        or document.get("case_count") != 65
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("dataset_sha256") != EXPECTED_DATABASE_SHA256
        or not isinstance(
            document.get("frozen_source_behavior_facts"), dict
        )
        or len(cast(list[object], document.get("source_artifacts", [])))
        != 1
        or len(cast(list[object], document.get("support_artifacts", [])))
        != 5
    ):
        raise EvidenceBuildError("parity evidence changed")
    return {
        "case_count": document["case_count"],
        "frozen_source_behavior_facts": document[
            "frozen_source_behavior_facts"
        ],
        "parity_sha256": EXPECTED_PARITY_SHA256,
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


def build_wave34_evidence(
    *,
    catalog_path: Path,
    input_path: Path,
    parity_path: Path,
    report_path: Path,
) -> dict[str, object]:
    """Validate immutable inputs and return compact wave-34 evidence."""

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
    evidence = build_wave34_evidence(
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
