#!/usr/bin/env python3
"""Build frozen unbound-stochastic-selection closures for wave 38."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
BASE_CATALOG_SHA256 = (
    "01c54ea1d5ce2f578663d4639de5d2f12f6dc39b6a2158f4118a03cdc253753a"
)
BASE_CATALOG_FILE_SHA256 = (
    "4e47c7c8bb4c6160140f8d2578e594a14c7a86afc508ef3482bff872c1c33223"
)
EVIDENCE_SCHEMA_VERSION = (
    "BIG_LOTTO_STATIC_DISPOSITION_WAVE38_EVIDENCE_V1"
)
REVIEW_POLICY_VERSION = "BIG_LOTTO_FROZEN_SOURCE_DISPOSITION_REVIEW_V10"
REASON_CODE = (
    "UNBOUND_STOCHASTIC_NATIVE_SELECTION_WITHOUT_FROZEN_PRESTATE"
)
EXPECTED_BASE_STATUS_COUNTS = {
    "BACKTESTED": 78,
    "CLOSED_UNEXECUTABLE": 45,
    "DUPLICATE_ALIAS": 5,
    "OWNER_DECISION_REQUIRED": 93,
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
    "lottery_api/models/dynamic_ensemble_predictor.py": {
        "source_sha256": (
            "9d1dce6311e2ba6f49103e5348c9a6a8ec182598cbe8bec158208890caea0e54"
        ),
        "required_fragments": (
            "self.strategies['constrained'] = enhanced.constrained_predict",
            "for name, strategy in self.strategies.items():",
            "result = strategy(history, lottery_rules)",
            "selected = np.random.choice(",
            "return self._generate_multiple_bets(",
        ),
        "decisive_source_facts": (
            "The frozen predict entrypoint executes every registered base "
            "strategy, including EnhancedPredictor.constrained_predict.",
            "That registered selector performs unseeded NumPy weighted "
            "sampling, so even the single-ticket vote consumes unbound state.",
            "The multi-ticket completion path adds further unseeded NumPy "
            "choice operations and the source binds no RNG pre-state.",
        ),
        "status_reason": (
            "The frozen dynamic ensemble has no unique native ticket "
            "sequence because its normal prediction loop invokes an "
            "unseeded constrained selector and its multi-ticket path samples "
            "again. No seed or historical RNG pre-state is preserved."
        ),
    },
    "lottery_api/models/enhanced_predictor.py": {
        "source_sha256": (
            "7bd110ea9eab867f26bf63fe6e1f2857fdbd0effd844c3e2c26eb83a9f444592"
        ),
        "required_fragments": (
            "for _ in range(1000):",
            "selected = np.random.choice(candidates, size=pick_count, "
            "replace=False, p=probs)",
            "self.constrained_predict,",
            "for _ in range(500):",
            "selected = np.random.choice(top_candidates, size=pick_count, "
            "replace=False, p=probs)",
        ),
        "decisive_source_facts": (
            "The frozen constrained selector searches 1,000 unseeded "
            "weighted NumPy samples before returning a native ticket.",
            "The enhanced ensemble invokes that selector and performs "
            "another 500 unseeded weighted samples for its own ticket.",
            "Both callable selectors are published by the source test "
            "entrypoint without a seed or serialized RNG pre-state.",
        ),
        "status_reason": (
            "The frozen enhanced predictor exposes stochastic constrained "
            "and ensemble tickets whose search samples are not seed-bound. "
            "Their historical native order cannot be recovered by assigning "
            "a new post-hoc seed."
        ),
    },
    "lottery_api/models/mcts_portfolio_optimizer.py": {
        "source_sha256": (
            "2475434b6ed2dbab48e8e06a4cd40454250e6c24d2eee9ad9a4c8eaa3548f503"
        ),
        "required_fragments": (
            "bet1 = sorted(random.sample(combined_pool, self.pick_count))",
            "bet2 = sorted(random.sample(combined_pool, self.pick_count))",
            "p_idx = random.randint(0, 1)",
            "new_n = random.choice(",
            "portfolio = self.mcts.optimize(dms_candidates, ai_candidates)",
        ),
        "decisive_source_facts": (
            "The frozen optimizer initializes both native tickets through "
            "module-global random.sample.",
            "Its subsequent search mutates the current portfolio through "
            "unseeded randint and choice operations.",
            "The AlphaZeroPredictor returns that stochastic two-ticket "
            "portfolio without binding or serializing RNG state.",
        ),
        "status_reason": (
            "The frozen MCTS optimizer cannot reproduce one historical "
            "two-ticket portfolio because initialization and mutation both "
            "consume unbound module-global randomness."
        ),
    },
    "lottery_api/models/transformer_model.py": {
        "source_sha256": (
            "58662b208fee454ce3a93db4ae820863bceff14a60c1a6e3b0b4870c25ec5c5a"
        ),
        "required_fragments": (
            "torch.randn(1, self.num_patches, d_model)",
            "DataLoader(dataset, batch_size=batch_size, shuffle=True)",
            "if self.use_torch and not self.is_trained:",
            "self.train(history, lottery_rules, epochs=15, batch_size=8)",
            "predicted_numbers = self._predict_torch(history, lottery_rules)",
        ),
        "decisive_source_facts": (
            "The frozen torch backend initializes learned state and positional "
            "state with unbound PyTorch randomness.",
            "First prediction trains the new model through a shuffled "
            "DataLoader before selecting its ticket.",
            "The source binds neither RNG pre-state nor checkpoint identity, "
            "and backend availability also changes the executed selector.",
        ),
        "status_reason": (
            "The frozen Transformer first-use ticket depends on newly "
            "initialized, shuffled, unseeded training state and no checkpoint "
            "or historical RNG pre-state is preserved."
        ),
    },
    "lottery_api/models/multi_bet_optimizer.py": {
        "source_sha256": (
            "fd171e7f2a121f5e3b25063377694706c7acabf5c644ea9b7dd707051cc795ef"
        ),
        "required_fragments": (
            "('constrained', lambda h, r: "
            "self.enhanced.constrained_predict(h, r), 100)",
            "result = func(history, lottery_rules)",
            "def generate_diversified_bets(",
            "random_indices = random.sample(",
            "for num_bets in [3, 6, 8]:",
        ),
        "decisive_source_facts": (
            "The frozen diversified entrypoint evaluates a registered "
            "EnhancedPredictor constrained selector before portfolio ranking.",
            "That imported selector is unseeded, and this source also uses "
            "unseeded sample/shuffle/choice in multiple native bet builders.",
            "The published test entrypoint backtests 3/6/8-ticket portfolios "
            "without binding or restoring any RNG pre-state.",
        ),
        "status_reason": (
            "The frozen multi-bet optimizer cannot recover its native "
            "portfolios because its standard strategy collection consumes "
            "an unseeded constrained selector and its own portfolio builders "
            "contain additional unbound sampling."
        ),
    },
    "tools/backtest/benchmark_dual_bet.py": {
        "source_sha256": (
            "0d6d2be1b3a21c95d5e919fb55e2cb9475f69a19181997d5a031c71b50e49785"
        ),
        "required_fragments": (
            "def predict_optimized_ensemble(",
            "selected = np.random.choice(valid_range, size=pick_count, "
            "replace=False, p=mc_weights)",
            "predict_optimized_ensemble,",
            "predict_dual_bet_hybrid,",
            "predict_hot_cold_split,",
        ),
        "decisive_source_facts": (
            "The frozen benchmark's optimized-ensemble configuration builds "
            "Monte Carlo candidate tickets with unseeded NumPy choice.",
            "That stochastic configuration is one of the three source "
            "strategies run by the main benchmark, not a diagnostic-only p-value.",
            "No seed or serialized RNG pre-state is bound before rolling "
            "native two-ticket generation.",
        ),
        "status_reason": (
            "The frozen dual-bet benchmark includes an unseeded Monte Carlo "
            "native strategy, so its source-configuration portfolio sequence "
            "cannot be reproduced exactly."
        ),
    },
    "tools/benchmark_new_strategies.py": {
        "source_sha256": (
            "b297ac69391ac99f42f348b08da46c31c6ddcc0baa6bf2196511ad07f1535bd5"
        ),
        "required_fragments": (
            "optimizer.generate_diversified_bets(",
            "num_bets=3",
            "py_random.shuffle(all_pool)",
            "subset.extend(py_random.sample(",
            "methods['Random_3Bet']['hits'] += 1",
        ),
        "decisive_source_facts": (
            "The frozen benchmark emits a three-ticket Random Orthogonal "
            "Baseline by shuffling the complete number pool.",
            "That baseline is scored as a source strategy alongside the "
            "imported diversified, VAE, and frequency configurations.",
            "Neither the benchmark nor the imported diversified call binds "
            "an RNG pre-state for the resulting native configuration sequence.",
        ),
        "status_reason": (
            "The frozen new-strategies benchmark includes an unseeded "
            "three-ticket random baseline in its native configuration set "
            "and does not preserve the RNG state needed to replay it."
        ),
    },
    "tools/predict_biglotto_6bets_optimized.py": {
        "source_sha256": (
            "f8bf1f0ecd742544d74a17c0edbd44bfdd54f8a9879813feb89fcf7ff41f6ae7"
        ),
        "required_fragments": (
            "self.optimizer.generate_diversified_bets(",
            "num_bets=1",
            "random.sample(range(1, 50), 6)",
            "'strategy': 'Power Pivot (Fallback)'",
            "'strategy': 'Random Chaos'",
        ),
        "decisive_source_facts": (
            "The frozen six-bet entrypoint delegates its second native ticket "
            "to the unseeded diversified multi-bet optimizer.",
            "Its source also substitutes unseeded random.sample tickets when "
            "the power-pivot or entropy branches cannot supply a unique ticket.",
            "No branch identity, RNG pre-state, or emitted ticket ledger was "
            "preserved for causal historical replay.",
        ),
        "status_reason": (
            "The frozen optimized six-bet portfolio depends on an unseeded "
            "upstream diversified selector and contains unseeded native "
            "fallback tickets, with no historical RNG or branch ledger."
        ),
    },
    "tools/strategy_leaderboard.py": {
        "source_sha256": (
            "5af2848b20597058819a49fb34a5fd5c3c9a2f26a91d89232ff8b177e510a334"
        ),
        "required_fragments": (
            "def strat_random(",
            "bets.append(random.sample(range(1, self.max_num + 1), 6))",
            '("Random (Baseline) x2", self.strat_random, '
            '{"n_bets": 2}, 2)',
            "next_num = np.random.choice(",
            "lb.generate_report(periods=args.n)",
        ),
        "decisive_source_facts": (
            "The frozen leaderboard includes Random Baseline x2 as an "
            "explicit native strategy in every generated report.",
            "Its LSTM-AR strategy also samples each ticket position through "
            "unseeded NumPy choice and falls back to the same random strategy.",
            "The CLI report entrypoint binds no seed or serialized RNG "
            "pre-state before the rolling strategy runs.",
        ),
        "status_reason": (
            "The frozen leaderboard's actual strategy set contains unseeded "
            "two-ticket random and LSTM-AR selections, so its source-order "
            "native configurations cannot be replayed exactly."
        ),
    },
}


class EvidenceBuildError(ValueError):
    """Frozen source or catalog identity violates the wave-38 review."""


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
