#!/usr/bin/env python3
"""Build frozen direct/transitive stochastic closures for wave 39."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "660d35418eedb2c7daab0911fd4ade3aa33cd0ccbf479c78ac2a0366afa212a9"
)
BASE_CATALOG_FILE_SHA256 = (
    "0cde129c724bdf0048ad295a198c902d2e1f6e668321becbc998ab18b86c7cfa"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE39_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V11"
REASON_CODE = (
    "UNBOUND_OR_TRANSITIVE_STOCHASTIC_NATIVE_SELECTION_WITHOUT_"
    "FROZEN_PRESTATE"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 54,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 84,
}
FORBIDDEN_SEED_BINDINGS = (
    "manual_seed(",
    "random.seed(",
    "np.random.seed(",
    "set_random_seed(",
    "set_seed(",
    "use_deterministic_algorithms(",
)
CLOSED_METHOD_SPECS: dict[str, dict[str, object]] = {
    "lottery_api/models/auto_optimizer.py": {
        "source_sha256": (
            "7328cf15d87447754c22db959a0a3bd7d5acd458ea29c865043b01575f58d636"
        ),
        "required_fragments": (
            "'constrained': enhanced.constrained_predict",
            "for method_name, method_func in methods.items():",
            "self._quick_backtest(",
            "best = max(results, key=lambda x: "
            "(x['win_rate'], x['avg_matches']))",
            "return optimizer.find_optimal(draws, rules, lottery_type)",
        ),
        "decisive_source_facts": (
            "The frozen optimizer includes the unseeded enhanced constrained "
            "selector in every method/window search.",
            "Its stochastic historical scores can change which configuration "
            "is persisted and then used for the native ticket.",
            "The run_optimization entrypoint binds neither seed nor persisted "
            "RNG pre-state for that selection process.",
        ),
        "status_reason": (
            "The frozen auto-optimizer's chosen method and ticket can change "
            "with unbound constrained-selector samples; no causal RNG "
            "pre-state was saved with the optimized configuration."
        ),
    },
    "lottery_api/models/meta_learning.py": {
        "source_sha256": (
            "93da5e6fe3354a0242023054397cb39d07f3e87a031dda18efd82bdf27a25c1f"
        ),
        "required_fragments": (
            "self.model = self._build_model()",
            "nn.Linear(self.input_dim, self.hidden_dim)",
            "if self.use_torch and self.model is not None:",
            "predicted_numbers = self._predict_torch(",
            "logits = self.model(X)",
        ),
        "decisive_source_facts": (
            "The frozen torch path builds randomly initialized Linear layers "
            "when the predictor instance is constructed.",
            "predict immediately ranks logits from those untrained random "
            "weights; it loads no checkpoint and performs no deterministic reset.",
            "Torch availability switches the native selector to a different "
            "lightweight implementation, while no backend or RNG state is pinned.",
        ),
        "status_reason": (
            "The frozen meta-learning predictor selects tickets from "
            "untrained random PyTorch weights when torch is available and "
            "binds neither checkpoint, backend, seed, nor RNG pre-state."
        ),
    },
    "lottery_api/models/optimized_predictor.py": {
        "source_sha256": (
            "ea587dc9d257b2b7d295d5e7e345db2760ffb251da276fcadfa928fa4ca890df"
        ),
        "required_fragments": (
            "from .multi_bet_optimizer import MultiBetOptimizer",
            "self.multi_bet_optimizer = MultiBetOptimizer()",
            "result = self.multi_bet_optimizer.generate_diversified_bets(",
            "multi = optimized_predictor.predict_multi(",
            "'BIG_LOTTO', 6",
        ),
        "decisive_source_facts": (
            "The frozen multi-ticket API delegates its complete portfolio to "
            "MultiBetOptimizer.generate_diversified_bets.",
            "That upstream native selector is frozen-source closed for "
            "unbound stochastic constrained and portfolio paths.",
            "The published main entrypoint emits a six-ticket BIG_LOTTO "
            "portfolio without binding an RNG pre-state around that call.",
        ),
        "status_reason": (
            "The frozen optimized predictor's published multi-ticket output "
            "is a direct call into the unseeded diversified optimizer and "
            "does not preserve the state required to replay it."
        ),
    },
    "lottery_api/models/ultra_optimized_predictor.py": {
        "source_sha256": (
            "67e02f62b826d3dc40ae77369a143f66ec9d1e884d42e68586e6e8ebd60eac63"
        ),
        "required_fragments": (
            "'numbers': random.sample(",
            "if random.random() < repeat_prob:",
            "chosen_repeats = np.random.choice(",
            "consecutive_start = np.random.choice(",
            "combo = random.sample(range(min_num, max_num + 1), pick_count)",
        ),
        "decisive_source_facts": (
            "The frozen primary predict path repeatedly samples repeat, "
            "consecutive, and weighted remaining numbers.",
            "Insufficient-history and multi-bet paths also construct native "
            "tickets through unseeded Python/NumPy sampling.",
            "No entrypoint binds or serializes either RNG state before "
            "returning the selected ticket or portfolio.",
        ),
        "status_reason": (
            "The frozen ultra-optimized predictor is intrinsically "
            "stochastic on its normal and fallback ticket paths, with no "
            "preserved seed or RNG pre-state."
        ),
    },
    "tools/backtest_phase1_comparison.py": {
        "source_sha256": (
            "c9400489aee3671f5428423621ffe1a8b4b571a9c5e0da217ebf328f4e4a3db3"
        ),
        "required_fragments": (
            "from models.multi_bet_optimizer import MultiBetOptimizer",
            "self.optimizer = MultiBetOptimizer()",
            "result = self.optimizer.generate_diversified_bets(",
            "num_bets=7",
            "compare_systems(test_periods=50)",
        ),
        "decisive_source_facts": (
            "The frozen new-system comparison obtains each seven-ticket "
            "portfolio directly from the unseeded diversified optimizer.",
            "Those portfolios are the actual selections scored against each "
            "rolling target, not a diagnostic-only simulation.",
            "The comparison entrypoint binds no seed or serialized RNG "
            "pre-state around the upstream selector.",
        ),
        "status_reason": (
            "The frozen phase-one comparison cannot replay its seven-ticket "
            "new-system portfolios because they are transitive outputs of "
            "the unseeded diversified optimizer."
        ),
    },
    "tools/find_best_test_periods.py": {
        "source_sha256": (
            "f3174bd643473fb45c2a4b154ed4fefdeec83bfe1efa35555879cd31adc825b8"
        ),
        "required_fragments": (
            "from models.multi_bet_optimizer import MultiBetOptimizer",
            "self.optimizer = MultiBetOptimizer()",
            "result = self.optimizer.generate_diversified_bets(",
            "num_bets=7",
            "find_best_test_periods()",
        ),
        "decisive_source_facts": (
            "The frozen period search scores rolling seven-ticket portfolios "
            "returned by the unseeded diversified optimizer.",
            "Its chosen period and reported winning configuration therefore "
            "depend on missing upstream RNG state.",
            "The CLI entrypoint does not bind a seed or preserve the emitted "
            "native ticket ledger.",
        ),
        "status_reason": (
            "The frozen best-period search has no reproducible native "
            "portfolio or selected-period sequence because its rolling "
            "tickets come from an unseeded upstream optimizer."
        ),
    },
    "tools/generate_final_predictions.py": {
        "source_sha256": (
            "5add2d975c50bea9c8fe63162b703ee84ba9b06697a261b423ae8b5dfc5808fc"
        ),
        "required_fragments": (
            "from models.multi_bet_optimizer import MultiBetOptimizer",
            "optimizer = MultiBetOptimizer()",
            "res = optimizer.generate_diversified_bets(",
            "num_bets=4",
            "generate_predictions()",
        ),
        "decisive_source_facts": (
            "The frozen final-predictions entrypoint delegates its four "
            "native tickets to the unseeded diversified optimizer.",
            "Its meta configuration changes scoring inputs but does not bind "
            "the upstream constrained or portfolio RNG state.",
            "No source ticket ledger or RNG pre-state is preserved.",
        ),
        "status_reason": (
            "The frozen final-predictions script cannot reproduce its "
            "four-ticket output because it is a direct unseeded diversified "
            "optimizer call without a preserved pre-state."
        ),
    },
    "tools/generate_v7_predictions.py": {
        "source_sha256": (
            "e941ef56d900a8accf32b0e9d329cc6612dc6aaf435a0155c486ccaeede7a53d"
        ),
        "required_fragments": (
            "from lottery_api.models.multi_bet_optimizer import "
            "MultiBetOptimizer",
            "optimizer = MultiBetOptimizer()",
            "result = optimizer.generate_diversified_bets(",
            "num_bets=7",
            "generate_predictions('BIG_LOTTO')",
        ),
        "decisive_source_facts": (
            "The frozen V7 entrypoint returns seven tickets directly from "
            "the unseeded diversified optimizer.",
            "It supplies no seed, reset policy, or serialized upstream RNG "
            "pre-state for the call.",
            "The script immediately publishes those stochastic tickets as "
            "the BIG_LOTTO prediction.",
        ),
        "status_reason": (
            "The frozen V7 generator is a thin wrapper over the unseeded "
            "diversified optimizer and has no independent reproducible "
            "native ticket sequence."
        ),
    },
    "tools/predict_big_lotto_115000003.py": {
        "source_sha256": (
            "794d6ebebe47743d1dfe5236c4760a383f3078d74c3a55e3648979f1f0e07cef"
        ),
        "required_fragments": (
            "from models.multi_bet_optimizer import MultiBetOptimizer",
            "optimizer = MultiBetOptimizer()",
            "res = optimizer.generate_diversified_bets(",
            "num_bets=4",
            "predict()",
        ),
        "decisive_source_facts": (
            "The frozen draw-specific predictor obtains each four-ticket "
            "method portfolio from the unseeded diversified optimizer.",
            "Its own comment acknowledges an underlying random-zone path, "
            "but the caller sets no seed or pre-state.",
            "No emitted portfolio ledger was frozen with the source.",
        ),
        "status_reason": (
            "The frozen 115000003 predictor cannot recover its native "
            "four-ticket method portfolios because it delegates to an "
            "unseeded optimizer without preserving outputs or RNG state."
        ),
    },
    "tools/predict_biglotto_7bets_optimized.py": {
        "source_sha256": (
            "eda0e6bd148adae77c8592f59a99e05698dcd9acc521973c2deb20d3d3a79a83"
        ),
        "required_fragments": (
            "from models.multi_bet_optimizer import MultiBetOptimizer",
            "self.optimizer = MultiBetOptimizer()",
            "res_core = self.optimizer.generate_diversified_bets(",
            "num_bets=3",
            "bets = optimizer.generate_7bets(history, rules)",
        ),
        "decisive_source_facts": (
            "The frozen seven-bet generator uses three upstream diversified "
            "tickets as the leading native positions.",
            "That upstream selector is closed for unbound stochastic state, "
            "and this wrapper provides no seed or reset policy.",
            "The remaining deterministic ticket logic cannot restore the "
            "missing first three ordered native tickets.",
        ),
        "status_reason": (
            "The frozen optimized seven-bet portfolio cannot be replayed "
            "because its first three ordered tickets are transitive outputs "
            "of the unseeded diversified optimizer."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-39 review."""


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
        if any(fragment in text for fragment in FORBIDDEN_SEED_BINDINGS):
            raise EvidenceBuildError(
                f"unbound randomness premise changed: {method_id}"
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
