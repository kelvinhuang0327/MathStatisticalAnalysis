#!/usr/bin/env python3
"""Build frozen-source duplicate-alias evidence for wave 42."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "2296f709d572f62dd4a77033cd8a5d7e5ac62cc57c7c718d4e20392636998b3a"
)
BASE_CATALOG_FILE_SHA256 = (
    "bc95d77aa4c6b4e68e511f80224111ba7cb685017932256b2367e124ca1699cd"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE42_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V6"
REASON_CODE = "PASS_THROUGH_WRAPPER_WITHOUT_INDEPENDENT_SELECTION_LOGIC"
TARGET_METHOD_ID = "lottery_api/models/advanced_strategies.py"
TARGET_STRATEGY_ID = (
    "legacy_biglotto__advanced_strategies__91c682887cd0"
)
TARGET_SOURCE_SHA256 = (
    "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
)
TARGET_BLOB_ID = "02dfb9fa99571fdef768c78500f6d83285e64508"
ALIAS_SPECS: dict[str, dict[str, str]] = {
    "tools/predict_v9_anomaly_cluster.py": {
        "entrypoint": "predict_next_draw",
        "source_sha256": (
            "e44a6f1f3466b3a332a45a0f3462291a906807105f7f2eaa890d0288dbc417a1"
        ),
        "source_blob_id": "5280cb10c958be37b64ca39542a683b7eee66b57",
        "source_function_ast_sha256": (
            "ca134f678933cb9e3664ef10a118303aea2143a441dd2cb1bfb311b85d10385a"
        ),
        "target_symbol": "anomaly_cluster_predict",
        "target_symbol_ast_sha256": (
            "64e34a215f9e0fa0cdd2a8e3c8dc16f378697f2a37214e9b77f2c908a7e7a857"
        ),
    },
    "tools/final_draw_v11.py": {
        "entrypoint": "generate_draw_report",
        "source_sha256": (
            "9b2b5dcb8a0bca65a108a15ad57e698cbc5522ee580a6ed8384ce59f5885981e"
        ),
        "source_blob_id": "dd26e16223c51c2edd5c027e63600a5e78d81140",
        "source_function_ast_sha256": (
            "9897cbef8a750633314f2ad388ff40c901ac729cf03c865ccd7b2071f3ad8c2f"
        ),
        "target_symbol": "anomaly_cluster_v11_predict",
        "target_symbol_ast_sha256": (
            "71ea70e26d813833d44c72b00c7f8eccc2da34d9db9b5b8f5d0d9227cb8c7731"
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-42 review."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _git(frozen_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ("git", "-C", str(frozen_root), *arguments),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EvidenceBuildError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _read_catalog(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        hashlib.sha256(raw).hexdigest() != BASE_CATALOG_FILE_SHA256
        or catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 80,
            "CLOSED_UNEXECUTABLE": 64,
            "DUPLICATE_ALIAS": 5,
            "OWNER_DECISION_REQUIRED": 72,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def _source_identity(
    frozen_root: Path,
    method_id: str,
    expected_sha256: str,
    expected_blob_id: str,
) -> bytes:
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        .decode("ascii")
        .strip()
    )
    if (
        hashlib.sha256(raw).hexdigest() != expected_sha256
        or blob_id != expected_blob_id
    ):
        raise EvidenceBuildError(
            f"frozen source identity changed: {method_id}"
        )
    return raw


def _function(
    tree: ast.Module,
    name: str,
    *,
    context: str,
) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise EvidenceBuildError(f"{context} entrypoint changed")
    return matches[0]


def _target_symbol(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "AdvancedStrategies"
    ]
    if len(classes) != 1:
        raise EvidenceBuildError("AdvancedStrategies class changed")
    matches = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise EvidenceBuildError(f"target symbol changed: {name}")
    return matches[0]


def _ast_sha256(node: ast.AST) -> str:
    return hashlib.sha256(
        ast.dump(
            node,
            annotate_fields=True,
            include_attributes=False,
        ).encode("utf-8")
    ).hexdigest()


def _validate_alias_wrapper(
    raw: bytes,
    *,
    method_id: str,
    spec: dict[str, str],
    target_tree: ast.Module,
) -> dict[str, object]:
    try:
        tree = ast.parse(raw, filename=method_id)
    except SyntaxError as exc:
        raise EvidenceBuildError(
            f"alias source cannot be parsed: {method_id}"
        ) from exc
    imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module
        == "lottery_api.models.advanced_strategies"
        and any(
            alias.name == "AdvancedStrategies"
            for alias in node.names
        )
        for node in tree.body
    )
    entrypoint = _function(
        tree,
        spec["entrypoint"],
        context=method_id,
    )
    calls = [
        node
        for node in ast.walk(entrypoint)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == spec["target_symbol"]
    ]
    bet_assignments = [
        node
        for node in ast.walk(entrypoint)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id in {"bets", "big_bets"}
            for target in node.targets
        )
        and isinstance(node.value, ast.Subscript)
    ]
    target_symbol = _target_symbol(
        target_tree,
        spec["target_symbol"],
    )
    if (
        not imported
        or len(calls) != 1
        or len(bet_assignments) != 1
        or _ast_sha256(entrypoint)
        != spec["source_function_ast_sha256"]
        or _ast_sha256(target_symbol)
        != spec["target_symbol_ast_sha256"]
    ):
        raise EvidenceBuildError(
            f"alias pass-through semantics changed: {method_id}"
        )
    return {
        "alias_legacy_method_id": method_id,
        "alias_source_blob_id": spec["source_blob_id"],
        "alias_source_byte_size": len(raw),
        "alias_source_function_ast_sha256": (
            spec["source_function_ast_sha256"]
        ),
        "alias_source_sha256": spec["source_sha256"],
        "decisive_source_facts": [
            (
                "The wrapper imports AdvancedStrategies and invokes exactly "
                f"one {spec['target_symbol']} call for its BIG_LOTTO bets."
            ),
            (
                "The wrapper takes the upstream details['bets'] value and "
                "only formats or prints those tickets."
            ),
            (
                "No wrapper-local BIG_LOTTO number-selection rule creates "
                "an independent portfolio."
            ),
        ],
        "reason_code": REASON_CODE,
        "reproduction_status": "DUPLICATE_ALIAS",
        "target_legacy_method_id": TARGET_METHOD_ID,
        "target_strategy_id": TARGET_STRATEGY_ID,
        "target_symbol": spec["target_symbol"],
        "target_symbol_ast_sha256": (
            spec["target_symbol_ast_sha256"]
        ),
    }


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    """Validate both pass-through wrappers and return compact evidence."""

    catalog = _read_catalog(base_catalog_path)
    records = cast(list[object], catalog.get("records", []))
    by_method: dict[str, dict[str, Any]] = {}
    for candidate in records:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            by_method[method_id] = row
    if len(by_method) != 221:
        raise EvidenceBuildError("base catalog records changed")
    target_record = by_method.get(TARGET_METHOD_ID)
    target_raw = _source_identity(
        frozen_root,
        TARGET_METHOD_ID,
        TARGET_SOURCE_SHA256,
        TARGET_BLOB_ID,
    )
    if (
        target_record is None
        or target_record.get("strategy_id") != TARGET_STRATEGY_ID
        or target_record.get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or target_record.get("source_sha256") != TARGET_SOURCE_SHA256
        or target_record.get("source_blob_id") != TARGET_BLOB_ID
        or target_record.get("source_byte_size") != len(target_raw)
    ):
        raise EvidenceBuildError("alias target catalog identity changed")
    try:
        target_tree = ast.parse(
            target_raw,
            filename=TARGET_METHOD_ID,
        )
    except SyntaxError as exc:
        raise EvidenceBuildError("alias target cannot be parsed") from exc

    aliases: list[dict[str, object]] = []
    for method_id, spec in ALIAS_SPECS.items():
        raw = _source_identity(
            frozen_root,
            method_id,
            spec["source_sha256"],
            spec["source_blob_id"],
        )
        record = by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != spec["source_sha256"]
            or record.get("source_blob_id") != spec["source_blob_id"]
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"alias catalog identity changed: {method_id}"
            )
        aliases.append(
            _validate_alias_wrapper(
                raw,
                method_id=method_id,
                spec=spec,
                target_tree=target_tree,
            )
        )
    aliases.sort(
        key=lambda row: cast(str, row["alias_legacy_method_id"])
    )
    return {
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "duplicate_aliases": aliases,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "review_policy_version": REVIEW_POLICY_VERSION,
        "target_source": {
            "legacy_method_id": TARGET_METHOD_ID,
            "source_blob_id": TARGET_BLOB_ID,
            "source_byte_size": len(target_raw),
            "source_sha256": TARGET_SOURCE_SHA256,
            "strategy_id": TARGET_STRATEGY_ID,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--base-catalog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output}"
        )
    evidence = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "alias_count": 2,
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output": str(args.output),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
