#!/usr/bin/env python3
"""Build frozen-source closure and duplicate evidence for wave 18."""

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
    "6c86158c8ba85234896e2a7ae05f05b083a5cd9716b53d9c130fb95d07c7e336"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE18_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V5"
CLOSED_REASON_CODE = (
    "COMPARATIVE_IMPORTED_PREDICTOR_AUDIT_WITHOUT_"
    "INDEPENDENT_TARGET_PORTFOLIO"
)
ALIAS_REASON_CODE = (
    "FROZEN_SELECTION_FUNCTION_AST_IDENTICAL_IGNORING_DOCSTRING"
)
ALIAS_BODY_SHA256 = (
    "97ba09dbea86ef96dbc69164ac1cec90170effb71e5bfb549bdd7d3b64a60611"
)
ALIAS_METHOD_ID = "tools/verify_randomness_impact.py"
ALIAS_TARGET_METHOD_ID = "tools/verify_gemini_3bet_claim.py"
ALIAS_TARGET_STRATEGY_ID = (
    "legacy_biglotto__verify_gemini_3bet_claim__05734b9e2afe"
)
CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "tools/audit_raw_experts.py": {
        "source_sha256": (
            "771e17bc998ad369432fb42a36793d4e9669485ee8e331b30a0fb0a654974836"
        ),
        "required_fragments": (
            "perf = {'HPSB_DMS': Counter(), 'AI_V3': Counter(), 'RANDOM': Counter()}",
            "dms_res = hpsb.predict_hpsb_dms(history, rules)",
            "ai_res = ai_adapter.get_ai_prediction('transformer_v3', history, rules)",
            "r_bet = random.sample(range(1, 50), 6)",
            "m3_plus = sum(dist[h] for h in range(3, 7))",
        ),
        "decisive_source_facts": (
            "The audit obtains HPSB_DMS and AI_V3 tickets by calling "
            "imported predictors without changing their number selection.",
            "Its locally sampled RANDOM ticket is explicitly the random "
            "comparison baseline, not the audited method's recommendation.",
            "The source only accumulates known-target match distributions "
            "and prints metrics; it returns no independent target portfolio.",
        ),
        "status_reason": (
            "The frozen program is a raw-expert comparison harness. Its "
            "non-random tickets belong to imported methods and its only "
            "local ticket is explicitly a random baseline, so assigning an "
            "independent strategy portfolio would double count or fabricate "
            "selection logic."
        ),
    },
    "tools/experimental/compare_models.py": {
        "source_sha256": (
            "adce89cc4bbcc8654794ab847e0b6f44085b629e7a77a4fe8543081c343f0906"
        ),
        "required_fragments": (
            "result = await model.predict(train_data, LOTTERY_RULES)",
            "models_to_test['Optimized Ensemble'] = EnsembleWrapper(ensemble)",
            "models_to_test['Frequency'] = FrequencyWrapper(unified_engine)",
            "models_to_test['Zone Balance'] = ZoneWrapper(unified_engine)",
            "best_model = max(results.items(), key=lambda x: x[1]['avg_hits'])",
        ),
        "decisive_source_facts": (
            "backtest_model accepts a caller-supplied model and only invokes "
            "that model's existing predict method against known targets.",
            "Every local wrapper is a pass-through to imported LSTM, "
            "ensemble, frequency, or zone-balance implementations.",
            "The only selection performed by this file is retrospective "
            "ranking of model metrics; it defines no independent ticket rule.",
        ),
        "status_reason": (
            "The frozen program compares imported models and ranks their "
            "known-result metrics. Its wrappers add no number-selection "
            "semantics, so an independent portfolio row would duplicate one "
            "of several upstream methods without a source-defined choice."
        ),
    },
}
ALIAS_SOURCE_SHA256 = {
    ALIAS_METHOD_ID: (
        "95c4b24121a543d86a28f804ac12ed81b7371f26ab7eaecf07b7896d4644593f"
    ),
    ALIAS_TARGET_METHOD_ID: (
        "05734b9e2afee57e9bfc3047a4cb3a79c9e4177c7bff38a13ed5a78c732fb978"
    ),
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-18 review."""


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
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _read_catalog(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_bytes())
    except json.JSONDecodeError as exc:
        raise EvidenceBuildError("base catalog is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise EvidenceBuildError("base catalog must be an object")
    catalog = cast(dict[str, Any], parsed)
    if (
        catalog.get("catalog_sha256") != BASE_CATALOG_SHA256
        or catalog.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or catalog.get("status_counts")
        != {
            "BACKTESTED": 43,
            "CLOSED_UNEXECUTABLE": 30,
            "DUPLICATE_ALIAS": 4,
            "OWNER_DECISION_REQUIRED": 144,
        }
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def _blob(
    frozen_root: Path,
    method_id: str,
    expected_sha256: str,
) -> tuple[bytes, str]:
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise EvidenceBuildError(
            f"frozen source SHA changed: {method_id}"
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
    return raw, blob_id


def _selection_body_sha256(raw: bytes, method_id: str) -> str:
    try:
        tree = ast.parse(raw, filename=method_id)
    except SyntaxError as exc:
        raise EvidenceBuildError(
            f"alias source cannot be parsed: {method_id}"
        ) from exc
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "generate_3bet_diversified"
    ]
    if len(functions) != 1:
        raise EvidenceBuildError(
            f"alias selection function changed: {method_id}"
        )
    node = functions[0]
    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    normalized = ast.FunctionDef(
        name="_",
        args=node.args,
        body=body,
        decorator_list=[],
        returns=None,
        type_comment=None,
        type_params=[],
    )
    payload = ast.dump(
        normalized,
        annotate_fields=True,
        include_attributes=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    catalog = _read_catalog(base_catalog_path)
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    record_by_method: dict[str, dict[str, Any]] = {}
    for candidate in cast(list[object], records_raw):
        if not isinstance(candidate, dict):
            raise EvidenceBuildError("base catalog record is invalid")
        row = cast(dict[str, Any], candidate)
        method_id = row.get("legacy_method_id")
        if isinstance(method_id, str):
            record_by_method[method_id] = row

    dispositions: list[dict[str, object]] = []
    for method_id, spec in CLOSED_METHOD_SPECS.items():
        expected_sha256 = cast(str, spec["source_sha256"])
        record = record_by_method.get(method_id)
        raw, blob_id = _blob(
            frozen_root,
            method_id,
            expected_sha256,
        )
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != expected_sha256
            or record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceBuildError(
                f"frozen source is not UTF-8: {method_id}"
            ) from exc
        if any(
            fragment not in text
            for fragment in cast(
                tuple[str, ...],
                spec["required_fragments"],
            )
        ):
            raise EvidenceBuildError(
                f"decisive frozen-source fact changed: {method_id}"
            )
        dispositions.append(
            {
                "decisive_source_facts": list(
                    cast(
                        tuple[str, ...],
                        spec["decisive_source_facts"],
                    )
                ),
                "legacy_method_id": method_id,
                "reason_code": CLOSED_REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": expected_sha256,
                "status_reason": spec["status_reason"],
            }
        )

    alias_rows: dict[str, dict[str, object]] = {}
    for method_id in (ALIAS_METHOD_ID, ALIAS_TARGET_METHOD_ID):
        expected_sha256 = ALIAS_SOURCE_SHA256[method_id]
        record = record_by_method.get(method_id)
        raw, blob_id = _blob(
            frozen_root,
            method_id,
            expected_sha256,
        )
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != expected_sha256
            or record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog alias identity changed: {method_id}"
            )
        body_sha256 = _selection_body_sha256(raw, method_id)
        if body_sha256 != ALIAS_BODY_SHA256:
            raise EvidenceBuildError(
                f"selection-function body changed: {method_id}"
            )
        alias_rows[method_id] = {
            "selection_function_body_sha256": body_sha256,
            "source_blob_id": blob_id,
            "source_byte_size": len(raw),
            "source_sha256": expected_sha256,
        }

    return {
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": dispositions,
        "duplicate_aliases": [
            {
                "alias_legacy_method_id": ALIAS_METHOD_ID,
                "alias_source": alias_rows[ALIAS_METHOD_ID],
                "decisive_source_facts": [
                    "Both frozen files define generate_3bet_diversified "
                    "with identical parameters and executable AST after "
                    "removing only their explanatory docstrings.",
                    "The shared function applies the same Deviation 2.0, "
                    "Markov 1.5, and Statistical 1.0 weights and returns the "
                    "same three fixed Top-18 slices.",
                    "The randomness-impact wrapper repeats that same "
                    "selection function under seed experiments; it does not "
                    "define a second portfolio algorithm.",
                ],
                "reason_code": ALIAS_REASON_CODE,
                "reproduction_status": "DUPLICATE_ALIAS",
                "selection_function_body_sha256": ALIAS_BODY_SHA256,
                "status_reason": (
                    "The frozen selection entrypoint is AST-identical to "
                    "verify_gemini_3bet_claim.py after removing docstrings. "
                    "The wrapper changes only the evaluation protocol, so "
                    "an independent ranking row would double count the same "
                    "three-ticket selection method."
                ),
                "target_legacy_method_id": ALIAS_TARGET_METHOD_ID,
                "target_source": alias_rows[ALIAS_TARGET_METHOD_ID],
                "target_strategy_id": ALIAS_TARGET_STRATEGY_ID,
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
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "disposition_count": len(
                    cast(list[object], document["dispositions"])
                ),
                "duplicate_alias_count": len(
                    cast(list[object], document["duplicate_aliases"])
                ),
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
