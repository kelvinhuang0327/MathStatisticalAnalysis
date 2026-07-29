#!/usr/bin/env python3
"""Build frozen direct/transitive stochastic closures for wave 56."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "1103e1ec10b1af374ef48c649dd32a3e9b72fb46f38d39c2921aaedd179bbf81"
)
BASE_CATALOG_FILE_SHA256 = (
    "f89e763a8d25a094ac2f0876b38cd37bd6e50a384306d985afd709ff43c95f71"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE56_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V12"
REASON_CODE = (
    "UNBOUND_DIRECT_OR_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_WITHOUT_"
    "FROZEN_PRESTATE"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 123,
    "CLOSED_UNEXECUTABLE": 65,
    "DUPLICATE_ALIAS": 11,
    "OWNER_DECISION_REQUIRED": 22,
}
CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "lottery_api/models/advanced_strategies.py": {
        "source_sha256": (
            "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
        ),
        "required_fragments": (
            "bets.append(expand_safe(random.randint(1, max_num), pairs_all))",
            "candidate = sorted(random.sample(outlier_pool, pick_count))",
            "return self.dynamic_ensemble_predict(history, lottery_rules)",
        ),
        "decisive_source_facts": (
            "The frozen public entropy-outlier selector samples fifty candidate "
            "tickets through module-global random.sample.",
            "Structural V3 and V11 portfolio completion also use module-global "
            "random.randint when their native positional portfolios are short.",
            "The source binds no seed or serialized Python RNG pre-state for "
            "these published BIG_LOTTO selection paths.",
        ),
        "status_reason": (
            "The frozen AdvancedStrategies source contains source-native "
            "stochastic ticket and portfolio-completion paths whose historical "
            "Python RNG pre-state was never preserved."
        ),
    },
    "lottery_api/models/big_lotto_dual_bet_optimizer.py": {
        "source_sha256": (
            "4f4e30404e4380c5d25439e2f02605de5cbbd1f9a0ead21822c5aa676062e0c5"
        ),
        "required_fragments": (
            "('ensemble', lambda: self.engine.ensemble_predict(history[:200], lottery_rules))",
            "bet1 = self.select_consensus_numbers(history, lottery_rules, pick_count)",
            "bet2 = self.select_gap_regression_numbers(",
        ),
        "decisive_source_facts": (
            "The first native dual-bet position always includes the frozen "
            "UnifiedPredictionEngine ensemble in its consensus vote.",
            "That ensemble executes monte_carlo_predict, whose 20,000 NumPy "
            "choice samples consume module-global unseeded state.",
            "The dual-bet source binds no NumPy seed or serialized upstream RNG "
            "pre-state before returning its ordered two-ticket portfolio.",
        ),
        "status_reason": (
            "The frozen dual-bet optimizer's leading consensus ticket is a "
            "transitive output of an unseeded Monte Carlo ensemble, so its "
            "historical ordered pair is not uniquely recoverable."
        ),
    },
    "lottery_api/models/selective_ensemble.py": {
        "source_sha256": (
            "423bd30a0a94b5c14599f490a5f882116c4e88d3fbe9afa53a8d63c58b751bf2"
        ),
        "required_fragments": (
            "'ensemble': prediction_engine.ensemble_predict",
            "('ensemble', 200, 3.45)",
            "selected = sorted(np.random.choice(top_nums, pick_count, replace=False).tolist())",
        ),
        "decisive_source_facts": (
            "The frozen BIG_LOTTO primary configuration always executes the "
            "UnifiedPredictionEngine ensemble at window 200.",
            "That upstream ensemble consumes unseeded NumPy Monte Carlo samples; "
            "the local fallback also calls unseeded np.random.choice directly.",
            "Neither the rolling backtest nor the prediction entrypoint binds or "
            "serializes the required NumPy RNG pre-state.",
        ),
        "status_reason": (
            "The frozen SelectiveEnsemble cannot reproduce one historical "
            "ticket because its standard BIG_LOTTO vote and fallback both "
            "depend on unbound NumPy selection state."
        ),
    },
    "lottery_api/models/unified_predictor.py": {
        "source_sha256": (
            "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
        ),
        "required_fragments": (
            "for _ in range(simulations):",
            "selected = np.random.choice(",
            "('monte_carlo', self.monte_carlo_predict, 1.0)",
        ),
        "decisive_source_facts": (
            "The frozen public monte_carlo_predict performs 20,000 weighted "
            "NumPy choice samples for every native ticket.",
            "The public ensemble_predict registers that stochastic method in "
            "its normal static strategy set, not as a diagnostic baseline.",
            "The module has no NumPy seed/reset or serialized NumPy RNG pre-state "
            "covering either published selection path.",
        ),
        "status_reason": (
            "The frozen unified predictor exposes native Monte Carlo and "
            "ensemble ticket paths whose NumPy RNG state was not bound, so a "
            "single frozen source-native portfolio cannot be recovered."
        ),
    },
    "tools/auto_optimizer_v2.py": {
        "source_sha256": (
            "d3238f515f54b6422a4851cbb9f867bc1536abde55acb4aaa69712fc7a6a508a"
        ),
        "required_fragments": (
            "sample_draws = test_draws if len(test_draws) < 20 else random.sample(test_draws, 20)",
            "r = random.randint(self.rules['minNumber'], self.rules['maxNumber'])",
            "parser.add_argument('--genetic', action='store_true'",
        ),
        "decisive_source_facts": (
            "The published genetic configuration samples its evaluation draws "
            "through unseeded module-global random.sample.",
            "Its normal single- and multi-ticket completion paths can also fill "
            "missing legal numbers with unseeded random.randint.",
            "The CLI exposes these as native prediction configurations without "
            "binding or persisting Python RNG state.",
        ),
        "status_reason": (
            "The frozen Auto Optimizer V2 configuration set includes unseeded "
            "genetic selection and native ticket-completion paths, with no "
            "historical Python RNG pre-state."
        ),
    },
    "tools/backtest/big_lotto_2025_tournament.py": {
        "source_sha256": (
            "bd7616eaae0945290e6e686c449a0637d6e04ec1ec0e972e2f96e763c9733dfd"
        ),
        "required_fragments": (
            '"monte_carlo": self.engine.monte_carlo_predict',
            "ranked_strategies = sorted(self.strategies.keys(),",
            'self.stats["Meta_Top2_DualBet"]',
        ),
        "decisive_source_facts": (
            "The frozen tournament scores unseeded monte_carlo_predict tickets "
            "as one of the strategies used by its recent-performance meta rank.",
            "Those stochastic outcomes can change both Meta_BestRecent and the "
            "ordered Meta_Top2_DualBet native selections.",
            "The tournament binds no NumPy seed or serialized RNG pre-state "
            "before its rolling strategy and meta-selection loop.",
        ),
        "status_reason": (
            "The frozen tournament's source-defined meta tickets depend on "
            "unseeded Monte Carlo results that can change the chosen upstream "
            "methods; no historical state or ticket ledger was saved."
        ),
    },
    "tools/predict_114000118.py": {
        "source_sha256": (
            "42c5b74e1ea7957ebaeb5151b89e15531694b2189e1ccf6477d19a8a4ff144ba"
        ),
        "required_fragments": (
            '"monte_carlo": engine.monte_carlo_predict',
            "ranked_strategies = sorted(strategies.keys(),",
            "pred_second = strategies[second_best_strategy_name]",
        ),
        "decisive_source_facts": (
            "The frozen draw-specific meta-selector includes unseeded Monte "
            "Carlo tickets in every recent-ten-draw performance audit.",
            "That stochastic audit can change both the best and second-best "
            "methods whose tickets are published for draw 114000118.",
            "The source binds no NumPy seed and preserves neither RNG pre-state "
            "nor the emitted ordered two-ticket portfolio.",
        ),
        "status_reason": (
            "The frozen 114000118 meta prediction cannot recover its two "
            "published tickets because its method ranking depends on unseeded "
            "Monte Carlo audit outputs."
        ),
    },
    "tools/verify_cluster_size.py": {
        "source_sha256": (
            "fdb1cdbd08b6d548f7615ce4df992b992c8a00a5c103f8cecf9d0f37add8ff0d"
        ),
        "required_fragments": (
            "res = engine.ensemble_predict(window, rules)",
            "for cluster_size in [15, 18]:",
            "return [bet1, bet2]",
        ),
        "decisive_source_facts": (
            "Both frozen cluster-size configurations call ensemble_predict at "
            "window 50 and window 200 before forming their native two tickets.",
            "The upstream ensemble executes unseeded NumPy Monte Carlo sampling, "
            "so the elite ranking and both tickets can vary.",
            "The source binds no NumPy seed or emitted-ticket ledger for either "
            "cluster-size configuration.",
        ),
        "status_reason": (
            "The frozen cluster-size verifier's two source configurations "
            "depend on an unseeded upstream ensemble, so their ordered native "
            "tickets cannot be exactly reconstructed."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-56 review."""


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


def _frozen_source(
    frozen_root: Path,
    path: str,
    expected_sha256: str,
) -> tuple[bytes, str]:
    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{path}",
    )
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise EvidenceBuildError(f"frozen source SHA changed: {path}")
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        .decode("ascii")
        .strip()
    )
    return raw, blob_id


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
        or catalog.get("status_counts") != EXPECTED_BASE_STATUS_COUNTS
        or catalog.get("full_universe_complete") is not False
    ):
        raise EvidenceBuildError("base catalog identity changed")
    return catalog


def build_evidence(
    *,
    frozen_root: Path,
    base_catalog_path: Path,
) -> dict[str, object]:
    catalog = _read_catalog(base_catalog_path)
    records_raw = catalog.get("records")
    if not isinstance(records_raw, list):
        raise EvidenceBuildError("base catalog records are missing")
    record_by_method = {
        cast(str, row["legacy_method_id"]): row
        for candidate in cast(list[object], records_raw)
        if isinstance(candidate, dict)
        for row in (cast(dict[str, Any], candidate),)
        if isinstance(row.get("legacy_method_id"), str)
    }
    if len(record_by_method) != 221:
        raise EvidenceBuildError("base catalog record count changed")

    dispositions: list[dict[str, object]] = []
    for method_id, spec in CLOSED_METHOD_SPECS.items():
        source_sha256 = cast(str, spec["source_sha256"])
        raw, blob_id = _frozen_source(
            frozen_root,
            method_id,
            source_sha256,
        )
        record = record_by_method.get(method_id)
        if (
            record is None
            or record.get("reproduction_status")
            != "OWNER_DECISION_REQUIRED"
            or record.get("source_sha256") != source_sha256
            or record.get("source_blob_id") != blob_id
            or record.get("source_byte_size") != len(raw)
        ):
            raise EvidenceBuildError(
                f"catalog method identity changed: {method_id}"
            )
        text = raw.decode("utf-8")
        required = cast(tuple[str, ...], spec["required_fragments"])
        if any(fragment not in text for fragment in required):
            raise EvidenceBuildError(
                f"decisive source fact changed: {method_id}"
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
                "reason_code": REASON_CODE,
                "reproduction_status": "CLOSED_UNEXECUTABLE",
                "source_blob_id": blob_id,
                "source_byte_size": len(raw),
                "source_sha256": source_sha256,
                "status_reason": spec["status_reason"],
            }
        )

    return {
        "base_catalog_file_sha256": BASE_CATALOG_FILE_SHA256,
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
    evidence = build_evidence(
        frozen_root=args.frozen_root,
        base_catalog_path=args.base_catalog,
    )
    payload = _canonical_bytes(evidence) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
                "output_file": str(args.output_file),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
