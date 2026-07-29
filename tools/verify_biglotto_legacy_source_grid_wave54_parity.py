#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate wave-54 one-shot portfolios in the frozen legacy runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)
from verify_biglotto_legacy_source_grid_wave48_parity import (
    ParityError,
    _alias_candidates,
    _canonical_bytes,
    _load_prior_ledger,
    _source_artifact,
    _validate_ticket,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_"
    "FROZEN_MODULES_PYTHON_RANDOM_RESET_SEED42_PER_TARGET"
)
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE54_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE54_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

CONSENSUS_METHOD_ID = "tools/predict_consensus_ensemble.py"
EVOLUTIONARY_GUM_METHOD_ID = "tools/predict_evolutionary_gum.py"

SOURCE_SHA256_BY_METHOD = {
    CONSENSUS_METHOD_ID: (
        "3ceb975a355c1912bab79134cd6a921140aaf50d97d83cf10639bf4d48a72be2"
    ),
    EVOLUTIONARY_GUM_METHOD_ID: (
        "b3e96cf483b05793f75811379ce284b98a0200767d5d5f35476b5bb47b1a52ab"
    ),
}
DEPENDENCY_SHA256_BY_PATH = {
    "lottery_api/models/advanced_strategies.py": (
        "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
    ),
    "lottery_api/models/unified_predictor.py": (
        "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
    ),
    "tools/data/best_config_BIG_LOTTO.json": (
        "a1d39f6a86924293d22e71573ea1a7825d62658267c9bb0e7c5a679d9d1459d0"
    ),
    "tools/data/frontier_library_BIG_LOTTO.json": (
        "cd6dee02bfdda3073755f74dfe2be77b74f68415e02afccf1c445da6486b22ee"
    ),
    "tools/strategy_leaderboard.py": (
        "5af2848b20597058819a49fb34a5fd5c3c9a2f26a91d89232ff8b177e510a334"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    CONSENSUS_METHOD_ID: 50,
    EVOLUTIONARY_GUM_METHOD_ID: 150,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    CONSENSUS_METHOD_ID: "SOURCE_CLI_DEFAULT_WINDOW_50_FULL_CONTEXT_BOUNDARY",
    EVOLUTIONARY_GUM_METHOD_ID: "SOURCE_STABLE_RECIPE_WINDOW_150_FULL_CONTEXT_BOUNDARY",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    CONSENSUS_METHOD_ID: 2,
    EVOLUTIONARY_GUM_METHOD_ID: 2,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    CONSENSUS_METHOD_ID: (
        "BEST_CONFIG_BIG_LOTTO_WINDOW50_PRUNED_2BET",
    ),
    EVOLUTIONARY_GUM_METHOD_ID: (
        "REGIME_SELECTED_FRONTIER_OR_STABLE_RECIPE_PRUNED_2BET",
    ),
}
SOURCE_CONFIGURATION_COUNT_BY_METHOD = {
    method_id: len(members)
    for method_id, members in SOURCE_CONFIGURATION_MEMBERS_BY_METHOD.items()
}
EXPECTED_OK_TARGET_COUNT_BY_METHOD = {
    method_id: 2149 - minimum
    for method_id, minimum in MINIMUM_HISTORY_BY_METHOD.items()
}

_REFERENCE_SCRIPT = r"""
import ast
import contextlib
import copy
import json
import logging
import os
import random
import sys
import importlib.util
import io

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api"), os.path.join(root, "tools")]

import numpy
import scipy

# The frozen audit recipe reaches UnifiedPredictionEngine.interval_predict,
# whose source uses Python's module-global RNG without setting a seed.
# Pin the otherwise missing execution input before loading or invoking it.
random.seed(42)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

draws = request["draws"]
minimums = request["minimum_history_by_method"]
consensus_id = "tools/predict_consensus_ensemble.py"
evolutionary_id = "tools/predict_evolutionary_gum.py"
outputs = {
    consensus_id: [None for _ in draws[1:]],
    evolutionary_id: [None for _ in draws[1:]],
}

with contextlib.redirect_stdout(io.StringIO()):
    consensus_module = load(
        consensus_id,
        "wave54_consensus",
    )
    consensus_lb = consensus_module.StrategyLeaderboard.__new__(
        consensus_module.StrategyLeaderboard
    )
    consensus_lb.lottery_type = "BIG_LOTTO"
    consensus_lb.max_num = 49
    consensus_lb.rules = {
        "minNumber": 1,
        "maxNumber": 49,
        "pickCount": 6,
        "name": "BIG_LOTTO",
    }
    consensus_lb._init_deep_models()
    consensus_engine = consensus_module.ConsensusEngine.__new__(
        consensus_module.ConsensusEngine
    )
    consensus_engine.lb = consensus_lb
    consensus_engine.lottery_type = "BIG_LOTTO"
    consensus_engine.max_num = 49
    with open(
        os.path.join(root, "tools/data/best_config_BIG_LOTTO.json"),
        encoding="utf-8",
    ) as recipe_stream:
        consensus_recipe = json.load(recipe_stream)
    for target_index in range(minimums[consensus_id], len(draws)):
        random.seed(42)
        consensus_engine.history = draws[:target_index]
        consensus_engine.config = copy.deepcopy(consensus_recipe)
        outputs[consensus_id][target_index - 1] = consensus_engine.predict(
            num_bets=2,
            window=50,
        )[0]

    evolutionary_module = load(
        evolutionary_id,
        "wave54_evolutionary_gum",
    )
    logging.disable(logging.CRITICAL)
    evolutionary_lb = evolutionary_module.StrategyLeaderboard.__new__(
        evolutionary_module.StrategyLeaderboard
    )
    evolutionary_lb.lottery_type = "BIG_LOTTO"
    evolutionary_lb.max_num = 49
    evolutionary_lb.rules = {
        "minNumber": 1,
        "maxNumber": 49,
        "pickCount": 6,
        "name": "BIG_LOTTO",
    }
    evolutionary_lb._init_deep_models()
    evolutionary_engine = evolutionary_module.EvolutionaryGUM.__new__(
        evolutionary_module.EvolutionaryGUM
    )
    evolutionary_engine.lb = evolutionary_lb
    evolutionary_engine.lottery_type = "BIG_LOTTO"
    evolutionary_engine.max_num = 49
    with open(
        os.path.join(root, "tools/data/frontier_library_BIG_LOTTO.json"),
        encoding="utf-8",
    ) as frontier_stream:
        frontier_library = json.load(frontier_stream)
    evolutionary_engine.stable_recipe = (
        evolutionary_engine.get_stable_recipe()
    )
    for target_index in range(minimums[evolutionary_id], len(draws)):
        random.seed(42)
        evolutionary_engine.history = draws[:target_index]
        evolutionary_engine.frontier_library = copy.deepcopy(frontier_library)
        outputs[evolutionary_id][target_index - 1] = (
            evolutionary_engine.predict(num_bets=2)[0]
        )

for sequence in outputs.values():
    for target_index, portfolio in enumerate(sequence):
        if portfolio is not None:
            sequence[target_index] = [
                [int(number) for number in ticket]
                for ticket in portfolio
            ]

json.dump(
    {
        "numpy_version": numpy.__version__,
        "outputs": outputs,
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "scipy_version": scipy.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


def _reference_outputs(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> dict[str, list[list[list[int]] | None]]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "minimum_history_by_method": MINIMUM_HISTORY_BY_METHOD,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
        cwd=frozen_source_directory,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen wave-54 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-54 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-54 reference runtime changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-54 reference method set changed")
    typed_outputs = cast(dict[str, object], raw_outputs)
    if set(typed_outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-54 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = typed_outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-54 ticket sequence changed")
        candidates = cast(list[object], raw_sequence)
        if len(candidates) != len(draws) - 1:
            raise ParityError("frozen wave-54 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(candidates):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-54 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-54 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-54 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def verify_wave54_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the complete wave-54 ledger and frozen-source parity proof."""

    source_artifacts = [
        _source_artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=sha256,
            role="ACTUAL_METHOD",
        )
        for path, sha256 in SOURCE_SHA256_BY_METHOD.items()
    ]
    source_artifacts.extend(
        _source_artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=sha256,
            role="SELECTION_LOGIC_DEPENDENCY",
        )
        for path, sha256 in DEPENDENCY_SHA256_BY_PATH.items()
    )
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    if len(pinned.draws) != 2149:
        raise ParityError("pinned BIG_LOTTO target count changed")
    draws: list[dict[str, object]] = [
        {
            "date": draw.draw_date.isoformat(),
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in pinned.draws
    ]
    targets = [draw.draw_number for draw in pinned.draws[1:]]
    contexts = [
        hashlib.sha256(
            json.dumps(
                [list(draw.numbers) for draw in pinned.draws[:target_index]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for target_index in range(1, len(pinned.draws))
    ]
    prior_targets, prior_contexts, prior_outputs = _load_prior_ledger(prior_ledger)
    if targets != prior_targets or contexts != prior_contexts:
        raise ParityError("regeneration database leaves the pinned logical history")
    outputs = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    ledger: dict[str, object] = {
        "context_numbers_sha256_by_target": contexts,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "minimum_history_by_method": MINIMUM_HISTORY_BY_METHOD,
        "minimum_history_rationale_by_method": MINIMUM_HISTORY_RATIONALE_BY_METHOD,
        "source_configuration_count_by_method": SOURCE_CONFIGURATION_COUNT_BY_METHOD,
        "source_configuration_members_by_method": SOURCE_CONFIGURATION_MEMBERS_BY_METHOD,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": targets,
        "tickets_by_method": outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(_canonical_bytes(ledger)).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "cross_wave_exact_alias_candidates": _alias_candidates(
            outputs,
            prior_outputs,
            cross_ledger=True,
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "exact_alias_candidates": _alias_candidates(
            outputs,
            outputs,
            cross_ledger=False,
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "intra_ticket_canonicalization_count_by_method": {
            method_id: 0 for method_id in SOURCE_SHA256_BY_METHOD
        },
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": sum(
            EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]
            * NATIVE_TICKET_COUNT_BY_METHOD[method_id]
            for method_id in SOURCE_SHA256_BY_METHOD
        ),
        "ok_target_count_by_method": EXPECTED_OK_TARGET_COUNT_BY_METHOD,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "ticket_sequence_sha256_by_method": {
            method_id: hashlib.sha256(_canonical_bytes(sequence)).hexdigest()
            for method_id, sequence in outputs.items()
        },
    }
    parity["parity_sha256"] = hashlib.sha256(_canonical_bytes(parity)).hexdigest()
    return ledger, parity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--frozen-source-directory", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--reference-python", default=Path("/usr/bin/python3"), type=Path)
    parser.add_argument("--prior-ledger", required=True, type=Path)
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, parity = verify_wave54_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
        prior_ledger=args.prior_ledger,
    )
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity_raw = _canonical_bytes(parity) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_raw)
    args.output_file.write_bytes(parity_raw)
    print(
        json.dumps(
            {
                "cross_wave_exact_alias_candidate_count": len(
                    cast(list[object], parity["cross_wave_exact_alias_candidates"])
                ),
                "exact_alias_candidate_count": len(
                    cast(list[object], parity["exact_alias_candidates"])
                ),
                "ledger_content_sha256": ledger["ledger_content_sha256"],
                "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
                "native_ticket_case_count": parity["native_ticket_case_count"],
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
