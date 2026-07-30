#!/usr/bin/env python3
"""Build frozen-source candidate-only closure evidence for wave 43."""

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
    "792ed501402cf371412515e7364a566bb1e8635fbc8eee74a1c2baf4aca8c468"
)
BASE_CATALOG_FILE_SHA256 = (
    "41c9f7b2d711b1c9f7105d204575d053a40799dee0d31a2e7bfc94809ce8898f"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE43_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V7"
REASON_CODE = (
    "VARIABLE_LENGTH_CANDIDATE_RECOMMENDATIONS_WITHOUT_"
    "SOURCE_DEFINED_LEGAL_TICKET"
)
METHOD_ID = "lottery_api/models/advanced_bayesian_analyzer.py"
SOURCE_SHA256 = (
    "8ad90229f37ae952679a66b8f6e3f43202b80210e3308eb1cdeecb7595f593fc"
)
SOURCE_BLOB_ID = "cd71d74f5cb450e648803cc7a7c607391bfa3c34"
METHOD_AST_SHA256 = {
    "analyze_number_bias": (
        "60cc668db865519f910fe2089817d344fdcd7c38dafcdf146bd770ac2d247d0a"
    ),
    "analyze_odd_even_bias": (
        "15a3109ccb71f5abf17e9a34994447227e57f8a6de6175f1fe77cafd47bb9cbd"
    ),
    "detect_state_regime": (
        "316afe9c2ea8a6b499e01a44b6b8a484462a4331a97472cd7793351c0844b469"
    ),
    "recommend_strategy": (
        "3c918ecbe91af1d79e72eb1201710c84cf8a9ce1d66b9a9feea981a28d4f07f8"
    ),
}
REQUIRED_FRAGMENTS = (
    "'numbers': [n['number'] for n in hot_numbers[:10]]",
    "'numbers': [n['number'] for n in cold_numbers[:10]]",
    "'suggested_ratio': '4奇2偶 或 5奇1偶'",
    "'suggested_ratio': '2奇4偶 或 1奇5偶'",
    "'recommendations': recommendations",
    "json.dump(output, f, indent=2, ensure_ascii=False)",
)


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-43 review."""


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
            "DUPLICATE_ALIAS": 7,
            "OWNER_DECISION_REQUIRED": 70,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def _ast_sha256(node: ast.AST) -> str:
    return hashlib.sha256(
        ast.dump(
            node,
            annotate_fields=True,
            include_attributes=False,
        ).encode("utf-8")
    ).hexdigest()


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    """Prove that the frozen analyzer never defines a legal ticket."""

    catalog = _read_catalog(base_catalog_path)
    records = cast(list[object], catalog.get("records", []))
    matches: list[dict[str, Any]] = []
    for candidate in records:
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        if row.get("legacy_method_id") == METHOD_ID:
            matches.append(row)
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
    )
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
        )
        .decode("ascii")
        .strip()
    )
    if (
        len(matches) != 1
        or matches[0].get("reproduction_status")
        != "OWNER_DECISION_REQUIRED"
        or matches[0].get("source_sha256") != SOURCE_SHA256
        or matches[0].get("source_blob_id") != SOURCE_BLOB_ID
        or matches[0].get("source_byte_size") != len(raw)
        or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256
        or blob_id != SOURCE_BLOB_ID
    ):
        raise EvidenceBuildError("wave-43 source identity changed")
    try:
        text = raw.decode("utf-8")
        tree = ast.parse(raw, filename=METHOD_ID)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise EvidenceBuildError("wave-43 source cannot be parsed") from exc
    if any(fragment not in text for fragment in REQUIRED_FRAGMENTS):
        raise EvidenceBuildError(
            "candidate-only source semantics changed"
        )
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "BayesianBiasAnalyzer"
    ]
    if len(classes) != 1:
        raise EvidenceBuildError("BayesianBiasAnalyzer changed")
    methods = {
        node.name: node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef)
    }
    actual_method_hashes = {
        name: _ast_sha256(methods[name])
        for name in METHOD_AST_SHA256
        if name in methods
    }
    if actual_method_hashes != METHOD_AST_SHA256:
        raise EvidenceBuildError("wave-43 method AST changed")
    return {
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": [
            {
                "candidate_k_semantics": (
                    "UP_TO_TEN_HOT_OR_COLD_RECOMMENDATION_CANDIDATES"
                ),
                "decisive_source_facts": [
                    (
                        "recommend_strategy emits independent hot and cold "
                        "candidate lists, each sliced to at most ten values."
                    ),
                    (
                        "Odd/even recommendations contain only a ratio and "
                        "do not identify six concrete numbers."
                    ),
                    (
                        "The source defines no candidate-to-ticket rule, "
                        "native ticket order, or legal six-number portfolio."
                    ),
                    (
                        "Taking the first six candidates would invent a new "
                        "method and conflate Candidate-K with ticket count."
                    ),
                ],
                "legacy_method_id": METHOD_ID,
                "method_ast_sha256": METHOD_AST_SHA256,
                "reason_code": REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": SOURCE_BLOB_ID,
                "source_byte_size": len(raw),
                "source_sha256": SOURCE_SHA256,
                "status_reason": (
                    "The frozen analyzer emits variable-length candidate "
                    "recommendations and parity-ratio guidance, but it never "
                    "defines a legal six-number ticket or a rule that converts "
                    "those candidates into an ordered native portfolio."
                ),
            }
        ],
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "review_policy_version": REVIEW_POLICY_VERSION,
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
                "disposition_count": 1,
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
