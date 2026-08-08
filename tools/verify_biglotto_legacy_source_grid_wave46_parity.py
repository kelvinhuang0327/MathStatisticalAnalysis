#!/usr/bin/env python3
"""Regenerate wave-46 deterministic portfolios in the frozen source runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE46_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE46_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

PORTFOLIO_OPTIMIZER_METHOD_ID = "ai_lab/automl_biglotto/portfolio_optimizer.py"
ORTHOGONAL_5BET_METHOD_ID = "tools/backtest_big_lotto_orthogonal_5bet.py"
SIX_BET_METHOD_ID = "tools/backtest_biglotto_6bet.py"
EWMA_SIX_BET_METHOD_ID = "tools/backtest_biglotto_6bet_ewma.py"
COLD_POOL_METHOD_ID = "tools/backtest_biglotto_coldpool_15.py"
MARKOV_4BET_METHOD_ID = "tools/backtest_biglotto_markov_4bet.py"
TRIPLE_STRIKE_V2_METHOD_ID = "tools/backtest_biglotto_triple_strike_v2.py"
MARKOV_REPEAT_METHOD_ID = "tools/backtest_markov_repeat_exception.py"
STRUCTURAL_GROUP_METHOD_ID = "tools/backtest_structural_group.py"
SUM_CONSTRAINT_METHOD_ID = "tools/backtest_sum_constraint.py"
OPTIMAL_MATRIX_METHOD_ID = "tools/optimal_2bet_3bet_matrix.py"
QUAD_STRIKE_METHOD_ID = "tools/predict_biglotto_quad_strike.py"
PREDICTABILITY_METHOD_ID = "tools/predictability_engine.py"

SOURCE_SHA256_BY_METHOD = {
    PORTFOLIO_OPTIMIZER_METHOD_ID: (
        "1a6efc7959b61fc400c037fe62fd143cfa2ad33d70c59f799326f1f196f55719"
    ),
    ORTHOGONAL_5BET_METHOD_ID: (
        "c4dff46c5a5eff0621cdfba64a623c0a36ad365a4912355b90d3a9ad1c8a0df0"
    ),
    SIX_BET_METHOD_ID: (
        "f5d8c03421d2be5f093233335d5fc28d7409eed54d203c788c4b9d46e53b1410"
    ),
    EWMA_SIX_BET_METHOD_ID: (
        "e1b5e100d254e2d77a5336b2d5a77675c65034d952c99940772b33d3d2332a08"
    ),
    COLD_POOL_METHOD_ID: (
        "2a80423e3cf5ee0d9543c0c7a43454a378c970d5f88edcb9b95117e4c5361223"
    ),
    MARKOV_4BET_METHOD_ID: (
        "aefb54eb345bf38fbeb1526959c12a3585a970325316dfbc2c6a7bb440b5ec6a"
    ),
    TRIPLE_STRIKE_V2_METHOD_ID: (
        "977a7cf65c8f8c5732d08edce53eb5250c9959992bf9718adb6cd3ec32a1bda5"
    ),
    MARKOV_REPEAT_METHOD_ID: (
        "9bd283fca5f3c543116b64cac512f41f889dadaf7cd646431cc83a62980ac071"
    ),
    STRUCTURAL_GROUP_METHOD_ID: (
        "2fc42ff67ab1e07c6a57adf9e9837ca5989163eff92c107c89f2b58d0081be0f"
    ),
    SUM_CONSTRAINT_METHOD_ID: (
        "acb3b118300ddeae322f98923e75bb85de2a8e8e13a9cf85c8d6bed10b9f5533"
    ),
    OPTIMAL_MATRIX_METHOD_ID: (
        "6e5aec296145ab1680cb90db65ba8265d7ed3b895ec26fc9506db8932d333c6e"
    ),
    QUAD_STRIKE_METHOD_ID: (
        "e202e664208faf3f998f93f4992a8e2595fe17f2179345bba8d4587deff48a36"
    ),
    PREDICTABILITY_METHOD_ID: (
        "6b456e12778745fafff402a779ba961291e215c58ce3f78d6f276b58dcefcaa2"
    ),
}
DEPENDENCY_SHA256_BY_PATH = {
    "ai_lab/automl_biglotto/config.py": (
        "3d30466c8a883934a43df563b406eded05e020da8df3371c19832c7088939a4f"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    PORTFOLIO_OPTIMIZER_METHOD_ID: 200,
    ORTHOGONAL_5BET_METHOD_ID: 500,
    SIX_BET_METHOD_ID: 200,
    EWMA_SIX_BET_METHOD_ID: 200,
    COLD_POOL_METHOD_ID: 300,
    MARKOV_4BET_METHOD_ID: 150,
    TRIPLE_STRIKE_V2_METHOD_ID: 500,
    MARKOV_REPEAT_METHOD_ID: 150,
    STRUCTURAL_GROUP_METHOD_ID: 150,
    SUM_CONSTRAINT_METHOD_ID: 150,
    OPTIMAL_MATRIX_METHOD_ID: 200,
    QUAD_STRIKE_METHOD_ID: 1,
    PREDICTABILITY_METHOD_ID: 200,
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    PORTFOLIO_OPTIMIZER_METHOD_ID: 5,
    ORTHOGONAL_5BET_METHOD_ID: 5,
    SIX_BET_METHOD_ID: 11,
    EWMA_SIX_BET_METHOD_ID: 17,
    COLD_POOL_METHOD_ID: 10,
    MARKOV_4BET_METHOD_ID: 27,
    TRIPLE_STRIKE_V2_METHOD_ID: 3,
    MARKOV_REPEAT_METHOD_ID: 24,
    STRUCTURAL_GROUP_METHOD_ID: 10,
    SUM_CONSTRAINT_METHOD_ID: 39,
    OPTIMAL_MATRIX_METHOD_ID: 5,
    QUAD_STRIKE_METHOD_ID: 4,
    PREDICTABILITY_METHOD_ID: 5,
}
SOURCE_CONFIGURATION_COUNT_BY_METHOD = {
    PORTFOLIO_OPTIMIZER_METHOD_ID: 1,
    ORTHOGONAL_5BET_METHOD_ID: 1,
    SIX_BET_METHOD_ID: 2,
    EWMA_SIX_BET_METHOD_ID: 3,
    COLD_POOL_METHOD_ID: 2,
    MARKOV_4BET_METHOD_ID: 7,
    TRIPLE_STRIKE_V2_METHOD_ID: 1,
    MARKOV_REPEAT_METHOD_ID: 6,
    STRUCTURAL_GROUP_METHOD_ID: 3,
    SUM_CONSTRAINT_METHOD_ID: 13,
    OPTIMAL_MATRIX_METHOD_ID: 1,
    QUAD_STRIKE_METHOD_ID: 1,
    PREDICTABILITY_METHOD_ID: 1,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    PORTFOLIO_OPTIMIZER_METHOD_ID: ("P3_VERIFIED_TS3_MARKOV_FREQ_ORTHO_5BET",),
    ORTHOGONAL_5BET_METHOD_ID: ("POWER_PRECISION_ORTHOGONAL_5BET",),
    SIX_BET_METHOD_ID: ("GENERATE_5BET", "GENERATE_6BET_LAG2_ECHO"),
    EWMA_SIX_BET_METHOD_ID: (
        "GENERATE_5BET",
        "GENERATE_6BET_EWMA_HIGH_DRIFT",
        "GENERATE_6BET_EWMA_LOW_DRIFT",
    ),
    COLD_POOL_METHOD_ID: ("COLD_POOL_SIZE_12", "COLD_POOL_SIZE_15"),
    MARKOV_4BET_METHOD_ID: (
        "TRIPLE_STRIKE_BASELINE",
        "TS3_MARKOV_DEFAULT_WINDOW_100",
        "TS3_MARKOV_SENSITIVITY_WINDOW_30",
        "TS3_MARKOV_SENSITIVITY_WINDOW_50",
        "TS3_MARKOV_SENSITIVITY_WINDOW_100",
        "TS3_MARKOV_SENSITIVITY_WINDOW_200",
        "TS3_MARKOV_SENSITIVITY_WINDOW_500",
    ),
    TRIPLE_STRIKE_V2_METHOD_ID: ("CYCLE_STRUCTURAL_EXTREME_TRIPLE",),
    MARKOV_REPEAT_METHOD_ID: (
        "MARKOV_REPEAT_BOOST_0_0_BASELINE",
        "MARKOV_REPEAT_BOOST_0_1",
        "MARKOV_REPEAT_BOOST_0_2",
        "MARKOV_REPEAT_BOOST_0_3",
        "MARKOV_REPEAT_BOOST_0_5",
        "MARKOV_REPEAT_BOOST_1_0",
    ),
    STRUCTURAL_GROUP_METHOD_ID: (
        "TRIPLE_STRIKE_BASELINE",
        "TS3_STRUCTURAL_REVERSION_4BET",
        "TS3_STRUCTURAL_COLD_3BET",
    ),
    SUM_CONSTRAINT_METHOD_ID: (
        "TRIPLE_STRIKE_BASELINE",
        "POOL_8_APPLY_ALL",
        "POOL_8_APPLY_BET2_ONLY",
        "POOL_8_APPLY_BET1_ONLY",
        "POOL_10_APPLY_ALL",
        "POOL_10_APPLY_BET2_ONLY",
        "POOL_10_APPLY_BET1_ONLY",
        "POOL_12_APPLY_ALL",
        "POOL_12_APPLY_BET2_ONLY",
        "POOL_12_APPLY_BET1_ONLY",
        "POOL_15_APPLY_ALL",
        "POOL_15_APPLY_BET2_ONLY",
        "POOL_15_APPLY_BET1_ONLY",
    ),
    OPTIMAL_MATRIX_METHOD_ID: ("ALL_FIVE_PRE_SELECTION_CANDIDATE_BETS",),
    QUAD_STRIKE_METHOD_ID: ("FOURIER_COLD_TAIL_GRAY_GAP_QUAD",),
    PREDICTABILITY_METHOD_ID: ("TS3_MARKOV_FREQ_ORTHO_LABEL_PORTFOLIO",),
}

EXPECTED_OK_TARGET_COUNT_BY_METHOD = {
    method_id: 2149 - minimum
    for method_id, minimum in MINIMUM_HISTORY_BY_METHOD.items()
}

_REFERENCE_SCRIPT = r"""
import importlib.util
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [
    root,
    os.path.join(root, "lottery_api"),
    os.path.join(root, "tools"),
]

import numpy
import scipy

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

import ai_lab.automl_biglotto.portfolio_optimizer as portfolio_optimizer

orthogonal = load(
    "tools/backtest_big_lotto_orthogonal_5bet.py",
    "wave46_orthogonal",
)
six_bet = load("tools/backtest_biglotto_6bet.py", "wave46_six_bet")
ewma = load("tools/backtest_biglotto_6bet_ewma.py", "wave46_ewma")
cold_pool = load(
    "tools/backtest_biglotto_coldpool_15.py",
    "wave46_cold_pool",
)
markov4 = load(
    "tools/backtest_biglotto_markov_4bet.py",
    "wave46_markov4",
)
triple_v2 = load(
    "tools/backtest_biglotto_triple_strike_v2.py",
    "wave46_triple_v2",
)
markov_repeat = load(
    "tools/backtest_markov_repeat_exception.py",
    "wave46_markov_repeat",
)
structural = load(
    "tools/backtest_structural_group.py",
    "wave46_structural",
)
sum_constraint = load(
    "tools/backtest_sum_constraint.py",
    "wave46_sum_constraint",
)
optimal = load(
    "tools/optimal_2bet_3bet_matrix.py",
    "wave46_optimal",
)
quad = load(
    "tools/predict_biglotto_quad_strike.py",
    "wave46_quad",
)
predictability = load(
    "tools/predictability_engine.py",
    "wave46_predictability",
)

draws = request["draws"]
minimums = request["minimum_history_by_method"]
method_ids = request["method_ids"]
outputs = {method_id: [] for method_id in method_ids}

for target_index in range(1, len(draws)):
    history = draws[:target_index]

    method_id = "ai_lab/automl_biglotto/portfolio_optimizer.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else portfolio_optimizer._p3_verified_5bet_strategy(history)
    )

    method_id = "tools/backtest_big_lotto_orthogonal_5bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else orthogonal.generate_big_lotto_orthogonal_5bet(history)
    )

    method_id = "tools/backtest_biglotto_6bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else six_bet.generate_5bet(history) + six_bet.generate_6bet(history)
    )

    method_id = "tools/backtest_biglotto_6bet_ewma.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            ewma.generate_5bet(history)
            + ewma.generate_6bet_high_drift(history)
            + ewma.generate_6bet_low_drift(history)
        )
    )

    method_id = "tools/backtest_biglotto_coldpool_15.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            cold_pool.generate_5bet(history, cold_pool_size=12)
            + cold_pool.generate_5bet(history, cold_pool_size=15)
        )
    )

    method_id = "tools/backtest_biglotto_markov_4bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            markov4.generate_triple_strike(history)
            + markov4.generate_ts3_markov4(history, markov_window=100)
            + markov4.generate_ts3_markov4(history, markov_window=30)
            + markov4.generate_ts3_markov4(history, markov_window=50)
            + markov4.generate_ts3_markov4(history, markov_window=100)
            + markov4.generate_ts3_markov4(history, markov_window=200)
            + markov4.generate_ts3_markov4(history, markov_window=500)
        )
    )

    method_id = "tools/backtest_biglotto_triple_strike_v2.py"
    if target_index < minimums[method_id]:
        outputs[method_id].append(None)
    else:
        b1 = triple_v2.strategy_cycle_momentum(history)
        b2 = triple_v2.strategy_structural_defense(history, exclude=set(b1))
        b3 = triple_v2.strategy_extreme_compensation(
            history,
            exclude=set(b1) | set(b2),
        )
        outputs[method_id].append([b1, b2, b3])

    method_id = "tools/backtest_markov_repeat_exception.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else sum(
            [
                markov_repeat.generate_ts3_markov4(
                    history,
                    markov_window=markov_repeat.MARKOV_WINDOW,
                    repeat_boost_factor=boost,
                )
                for boost in [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]
            ],
            [],
        )
    )

    method_id = "tools/backtest_structural_group.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            structural.generate_triple_strike(history)
            + structural.generate_ts3_structural(history)
            + structural.generate_ts3_structural_cold(history)
        )
    )

    method_id = "tools/backtest_sum_constraint.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            sum_constraint.generate_triple_strike(history)
            + sum(
                [
                    sum_constraint.generate_ts_sum_constrained(
                        history,
                        pool_size=pool_size,
                        apply_to=apply_to,
                    )
                    for pool_size in [8, 10, 12, 15]
                    for apply_to in ["all", "bet2_only", "bet1_only"]
                ],
                [],
            )
        )
    )

    method_id = "tools/optimal_2bet_3bet_matrix.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else optimal.generate_all_5_bets(history)
    )

    method_id = "tools/predict_biglotto_quad_strike.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else quad.generate_quad_strike(history)
    )

    method_id = "tools/predictability_engine.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else predictability.generate_5bet(history)
    )

json.dump(
    {
        "numpy_version": numpy.__version__,
        "outputs": outputs,
        "python_version": ".".join(
            str(item) for item in sys.version_info[:3]
        ),
        "scipy_version": scipy.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityError(ValueError):
    """Frozen source, runtime, or generated tickets violate the contract."""


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
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _source_artifact(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    path: str,
    expected_sha256: str,
    role: str,
) -> dict[str, str]:
    git_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{path}",
    )
    extracted_raw = frozen_source_directory.joinpath(path).read_bytes()
    if git_raw != extracted_raw or hashlib.sha256(git_raw).hexdigest() != expected_sha256:
        raise ParityError(f"frozen source identity changed: {path}")
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        .decode("ascii")
        .strip()
    )
    return {
        "path": path,
        "role": role,
        "sha256": expected_sha256,
        "source_blob_id": blob_id,
    }


def _validate_ticket(value: object, *, context: str) -> list[int]:
    if not isinstance(value, list):
        raise ParityError(f"{context}: source runtime ticket is not an array")
    numbers = cast(list[object], value)
    if (
        len(numbers) != 6
        or any(type(number) is not int for number in numbers)
        or len(set(numbers)) != 6
        or any(not 1 <= cast(int, number) <= 49 for number in numbers)
    ):
        raise ParityError(f"{context}: source runtime emitted an illegal ticket: {value!r}")
    return sorted(cast(list[int], numbers))


def _reference_outputs(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> tuple[dict[str, list[list[list[int]] | None]], dict[str, int]]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "method_ids": list(SOURCE_SHA256_BY_METHOD),
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
            or "frozen wave-46 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-46 reference emitted invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen wave-46 reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-46 reference runtime changed")
    outputs_raw = document.get("outputs")
    if not isinstance(outputs_raw, dict):
        raise ParityError("frozen wave-46 reference method outputs changed")
    outputs = cast(dict[str, object], outputs_raw)
    if set(outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-46 reference method set changed")
    expected_sequence_length = len(draws) - 1
    typed: dict[str, list[list[list[int]] | None]] = {}
    intra_ticket_canonicalization_count: dict[str, int] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-46 ticket sequence changed")
        sequence = cast(list[object], raw_sequence)
        if len(sequence) != expected_sequence_length:
            raise ParityError("frozen wave-46 target sequence changed")
        typed_sequence: list[list[list[int]] | None] = []
        ok_count = 0
        canonicalization_count = 0
        for candidate in sequence:
            if candidate is None:
                typed_sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-46 portfolio changed")
            raw_tickets = cast(list[object], candidate)
            tickets = [
                _validate_ticket(
                    ticket,
                    context=(f"{method_id} sequence {len(typed_sequence)} ticket {ticket_index}"),
                )
                for ticket_index, ticket in enumerate(raw_tickets, start=1)
            ]
            canonicalization_count += sum(
                isinstance(ticket, list) and ticket != sorted(cast(list[Any], ticket))
                for ticket in raw_tickets
            )
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-46 native count changed: {method_id}")
            typed_sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-46 eligible count changed: {method_id}")
        typed[method_id] = typed_sequence
        intra_ticket_canonicalization_count[method_id] = canonicalization_count
    return typed, intra_ticket_canonicalization_count


def _exact_alias_candidates(
    outputs: dict[str, list[list[list[int]] | None]],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for left, right in combinations(SOURCE_SHA256_BY_METHOD, 2):
        if NATIVE_TICKET_COUNT_BY_METHOD[left] != NATIVE_TICKET_COUNT_BY_METHOD[right]:
            continue
        overlapping = [
            (left_value, right_value)
            for left_value, right_value in zip(outputs[left], outputs[right], strict=True)
            if left_value is not None and right_value is not None
        ]
        mismatch_count = sum(
            left_value != right_value for left_value, right_value in overlapping
        )
        if overlapping and mismatch_count == 0:
            candidates.append(
                {
                    "left_method_id": left,
                    "overlapping_causal_output_case_count": len(overlapping),
                    "output_mismatch_count": 0,
                    "right_method_id": right,
                }
            )
    return candidates


def verify_wave46_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return a complete ledger and its frozen-source parity proof."""

    if expected_database_sha256 != PINNED_DATASET_SHA256:
        raise ParityError("wave-46 parity requires the pinned full dataset")
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
        require_replay_authority=False,
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
    outputs, canonicalization_counts = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    target_draw_numbers = [draw.draw_number for draw in pinned.draws[1:]]
    context_numbers_sha256 = [
        hashlib.sha256(
            json.dumps(
                [list(draw.numbers) for draw in pinned.draws[:target_index]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for target_index in range(1, len(pinned.draws))
    ]
    sequence_sha256_by_method = {
        method_id: hashlib.sha256(_canonical_bytes(sequence)).hexdigest()
        for method_id, sequence in outputs.items()
    }
    ledger: dict[str, object] = {
        "context_numbers_sha256_by_target": context_numbers_sha256,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "minimum_history_by_method": MINIMUM_HISTORY_BY_METHOD,
        "source_configuration_count_by_method": SOURCE_CONFIGURATION_COUNT_BY_METHOD,
        "source_configuration_members_by_method": SOURCE_CONFIGURATION_MEMBERS_BY_METHOD,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(_canonical_bytes(ledger)).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "dataset_sha256": pinned.database_sha256_before,
        "exact_alias_candidates": _exact_alias_candidates(outputs),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "intra_ticket_canonicalization_count_by_method": canonicalization_counts,
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
        "ticket_sequence_sha256_by_method": sequence_sha256_by_method,
    }
    parity["parity_sha256"] = hashlib.sha256(_canonical_bytes(parity)).hexdigest()
    return ledger, parity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--frozen-source-directory", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument(
        "--reference-python",
        default=Path("/usr/bin/python3"),
        type=Path,
    )
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, parity = verify_wave46_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
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
