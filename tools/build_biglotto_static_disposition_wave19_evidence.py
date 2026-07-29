#!/usr/bin/env python3
"""Build checked frozen-source closure evidence for wave 19."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "048eab0b352a030a3f38634b9c5122142e5a0749e4ae569104dfeb0b85065736"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE19_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V6"
NON_BIGLOTTO_REASON = "NON_BIG_LOTTO_FIXED_5_OF_39_SOURCE"
SYNTHETIC_HARNESS_REASON = (
    "SYNTHETIC_INPUT_IMPORTED_PREDICTOR_TEST_HARNESS"
)
COMPARATIVE_HARNESS_REASON = (
    "COMPARATIVE_IMPORTED_PREDICTOR_BACKTEST_WITHOUT_"
    "INDEPENDENT_TARGET_PORTFOLIO"
)

CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "tools/backtest_39lotto_comprehensive.py": {
        "source_sha256": (
            "c233ed549b92ffd537066a07e3c956966a8fd273d76d8fcbd9e7df5df4bf02ae"
        ),
        "reason_code": NON_BIGLOTTO_REASON,
        "required_fragments": (
            "WHERE lottery_type = 'DAILY_539'",
            "POOL = 39",
            "PICK = 5",
            "'lottery': '39樂合彩 (DAILY_539)'",
            "expected_overlap': PICK * PICK / POOL",
        ),
        "decisive_source_facts": (
            "The frozen loader selects only DAILY_539 rows and never loads "
            "BIG_LOTTO history.",
            "Every native strategy and exact baseline uses the fixed "
            "39-number pool and five-number ticket constants.",
            "The emitted result metadata explicitly identifies the lottery "
            "as 39 Lotto (DAILY_539), so a 6-of-49 portfolio would require "
            "inventing semantics absent from the source.",
        ),
        "status_reason": (
            "The frozen source is a DAILY_539 5-of-39 research program, not "
            "an executable BIG_LOTTO 6-of-49 method. It cannot be converted "
            "into a Big Lotto portfolio without changing its lottery, "
            "ticket size, baselines, and selection rules."
        ),
    },
    "tools/testing/test-optimization-simple.py": {
        "source_sha256": (
            "888431e7cfd2a448c13efb1671e45f1209fe3c831bdbdbb882309cbe19dd7713"
        ),
        "reason_code": SYNTHETIC_HARNESS_REASON,
        "required_fragments": (
            "numbers = sorted(random.sample(range(1, 50), 6))",
            "test_data = generate_test_data(100)",
            "result = prediction_engine.bayesian_predict(history, lottery_rules)",
            "result = prediction_engine.frequency_predict(history, lottery_rules)",
            "成功: {success_count}/{len(strategies)}",
        ),
        "decisive_source_facts": (
            "The source creates random synthetic draws instead of reading "
            "historical target draws.",
            "All displayed tickets are returned unchanged by four imported "
            "UnifiedPredictionEngine methods.",
            "The program checks call success and confidence output only; it "
            "defines no independent target-draw ticket or portfolio rule.",
        ),
        "status_reason": (
            "The frozen file is a synthetic smoke-test harness for imported "
            "Bayesian, Frequency, Odd-Even, and Hot-Cold methods. Treating "
            "the harness as a separate strategy would duplicate upstream "
            "selection logic and fabricate a source-native portfolio."
        ),
    },
    "tools/testing/test-optimization-b.py": {
        "source_sha256": (
            "bb1ae535163a9666f2c7b5fc2326c5cd2a5c8f0d44de736ede9fdce63c808750"
        ),
        "reason_code": SYNTHETIC_HARNESS_REASON,
        "required_fragments": (
            "numbers = sorted(random.sample(range(1, 50), 6))",
            "test_data = generate_test_data(150)",
            "result = prediction_engine.markov_predict(history, lottery_rules)",
            "result = prediction_engine.zone_balance_predict(history, lottery_rules)",
            "result = prediction_engine.sum_range_predict(history, lottery_rules)",
        ),
        "decisive_source_facts": (
            "The source creates random synthetic draws rather than using a "
            "real causal target history.",
            "Its three result branches pass through imported Markov, Zone "
            "Balance, and Sum Range predictors without selecting numbers.",
            "The local logic only evaluates returned confidence values "
            "against expected ranges and prints a test summary.",
        ),
        "status_reason": (
            "The frozen file is a synthetic confidence-test harness for "
            "three imported predictors. It contributes no independent "
            "number-selection or portfolio semantics that can be ranked "
            "without double counting those upstream methods."
        ),
    },
    "tools/testing/test-all-optimizations.py": {
        "source_sha256": (
            "c7bc2a0fe6f948834aa74308bba808908fd9201053f4ce6155b070df9a60952d"
        ),
        "reason_code": SYNTHETIC_HARNESS_REASON,
        "required_fragments": (
            "numbers = sorted(random.sample(range(1, 50), 6))",
            "test_data = generate_test_data(150)",
            "result = prediction_engine.bayesian_predict(history, lottery_rules)",
            "result = prediction_engine.markov_predict(history, lottery_rules)",
            "improvement = (confidence - baseline) / baseline * 100",
        ),
        "decisive_source_facts": (
            "The source constructs one random synthetic history and does "
            "not bind predictions to real historical target draws.",
            "Each of its seven branches directly calls an imported "
            "UnifiedPredictionEngine strategy and relays that result.",
            "Its only local computation compares confidence values with "
            "hard-coded targets; there is no portfolio composition rule.",
        ),
        "status_reason": (
            "The frozen file is an aggregate synthetic test of seven "
            "imported predictors. It adds confidence-reporting logic but no "
            "independent ticket-selection semantics, so a separate strategy "
            "row would duplicate the imported methods."
        ),
    },
    "tools/backtest_ml_comprehensive_2025_biglotto.py": {
        "source_sha256": (
            "a3e2b5b7e5b3117053385cf59611ce1c542a8f4291b3892b0f98d5cfccbad9a3"
        ),
        "reason_code": COMPARATIVE_HARNESS_REASON,
        "required_fragments": (
            "'頻率分析 (Frequency)': lambda h, r: engine.frequency_predict(h, r)",
            "'偏差分析 (Deviation)': lambda h, r: engine.deviation_predict(h, r)",
            "'Ensemble Stacking': lambda h, r: "
            "ensemble.predict_with_features(h, r, use_lstm=False)",
            "result = backtest_method(method_name, predict_func, "
            "all_draws, rules, test_periods)",
            "results.sort(key=lambda x: x['win_rate'], reverse=True)",
        ),
        "decisive_source_facts": (
            "The test-method table consists entirely of pass-through calls "
            "to seven UnifiedPredictionEngine methods and one imported "
            "EnsembleStackingPredictor.",
            "backtest_method scores whichever caller-supplied predictor it "
            "receives against known results and returns only metrics.",
            "The file retrospectively ranks those imported methods but never "
            "selects one as a source-defined target portfolio.",
        ),
        "status_reason": (
            "The frozen source is a comparative backtest and leaderboard for "
            "eight imported predictors. It defines no independent number "
            "selection or source-defined portfolio choice, so a separate "
            "ranking row would duplicate upstream strategies."
        ),
    },
}

EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 43,
    "CLOSED_UNEXECUTABLE": 32,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 141,
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-19 review."""


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
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
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
        raise EvidenceBuildError(f"frozen source SHA changed: {method_id}")
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
    if len(record_by_method) != 221:
        raise EvidenceBuildError("base catalog record count changed")

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
                "reason_code": spec["reason_code"],
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": expected_sha256,
                "status_reason": spec["status_reason"],
            }
        )

    return {
        "base_catalog_sha256": BASE_CATALOG_SHA256,
        "dispositions": dispositions,
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
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
