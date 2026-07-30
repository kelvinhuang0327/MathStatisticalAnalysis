#!/usr/bin/env python3
"""Regenerate wave-48 deterministic portfolios in the frozen source runtime."""

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
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE48_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE48_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

ENHANCEMENTS_METHOD_ID = "tools/backtest_biglotto_enhancements.py"
DIRECTION_3_METHOD_ID = "tools/backtest_direction_3.py"
OPTIMIZE_5BET_METHOD_ID = "tools/optimize_5bet_weights.py"

SOURCE_SHA256_BY_METHOD = {
    ENHANCEMENTS_METHOD_ID: (
        "b0bf78ef7e32ef1e07825251af45846076dbd331f6a1f2f8c89a08a1f301696e"
    ),
    DIRECTION_3_METHOD_ID: (
        "91f93b31efb5a4ffae1956929aea93b53f972424d80a27caf0e246b3f54c48cc"
    ),
    OPTIMIZE_5BET_METHOD_ID: (
        "fa736ab445cc7c39f77ebdcd9f01215a3a5ef2316eb8a65b359bf9565269a9a7"
    ),
}
DEPENDENCY_SHA256_BY_PATH = {
    "tools/evolving_strategy_engine/strategy_base.py": (
        "b9224ce1634482f751223752c7308233a8fd836b9e133facb95458edc85238ea"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    ENHANCEMENTS_METHOD_ID: 649,
    DIRECTION_3_METHOD_ID: 500,
    OPTIMIZE_5BET_METHOD_ID: 649,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    ENHANCEMENTS_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    DIRECTION_3_METHOD_ID: "SOURCE_MIN_BUFFER_500",
    OPTIMIZE_5BET_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    ENHANCEMENTS_METHOD_ID: 42,
    DIRECTION_3_METHOD_ID: 6,
    OPTIMIZE_5BET_METHOD_ID: 5,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    ENHANCEMENTS_METHOD_ID: (
        "BASE_TS3_MARKOV4",
        "P1_A_REGIME_ADAPTIVE_4BET",
        "P1_B_CONSECUTIVE_POST_PROCESSING_4BET",
        "P2_A_RANK_DIVERSITY_4BET",
        "P2_B_ANTI_CONSENSUS_5BET",
        "P3_A_AUTO_LEARNING_4BET",
        "P3_B_SEQUENCE_4BET",
        "COMBINED_P1_4BET",
        "COMBINED_ALL_4BET",
        "COMBINED_BEST_5BET",
    ),
    DIRECTION_3_METHOD_ID: (
        "TRIPLE_STRIKE_3BET",
        "STABILIZED_P0_P1_GRAY_GAP_3BET",
    ),
    OPTIMIZE_5BET_METHOD_ID: ("TS3_MARKOV_FREQUENCY_ORTHOGONAL_5BET",),
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
import importlib.util
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api"), os.path.join(root, "tools")]

import numpy
import scipy

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

enhancements = load("tools/backtest_biglotto_enhancements.py", "wave48_enhancements")
direction = load("tools/backtest_direction_3.py", "wave48_direction")
optimizer = load("tools/optimize_5bet_weights.py", "wave48_optimizer")

draws = request["draws"]
minimums = request["minimum_history_by_method"]
method_ids = request["method_ids"]
outputs = {method_id: [] for method_id in method_ids}
auto_learner = enhancements.AutoLearner(lookback=20)
enhancement_functions = (
    enhancements.generate_base_ts3m4,
    enhancements.generate_p1a_regime_adaptive,
    enhancements.generate_p1b_consecutive,
    enhancements.generate_p2a_rank_diversity,
    enhancements.generate_p2b_5bet_anti,
    auto_learner.generate,
    enhancements.generate_p3b_lstm_sequence,
    enhancements.generate_combined_p1,
    enhancements.generate_combined_all_4bet,
    enhancements.generate_combined_5bet,
)

for target_index in range(1, len(draws)):
    history = draws[:target_index]
    raw = numpy.asarray([item["numbers"] for item in history], dtype=numpy.int32)

    method_id = "tools/backtest_biglotto_enhancements.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else sum((function(history) for function in enhancement_functions), [])
    )

    method_id = "tools/backtest_direction_3.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            direction.triple_strike_predict(history)
            + direction.stabilized_p0p1_predict(history)
        )
    )

    method_id = "tools/optimize_5bet_weights.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else optimizer.generate_5bet_and_features(raw)[0]
    )

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
    git_raw = _git(frozen_root, "show", f"{FROZEN_SOURCE_COMMIT}:{path}")
    extracted_raw = frozen_source_directory.joinpath(path).read_bytes()
    if git_raw != extracted_raw or hashlib.sha256(git_raw).hexdigest() != expected_sha256:
        raise ParityError(f"frozen source identity changed: {path}")
    return {
        "path": path,
        "role": role,
        "sha256": expected_sha256,
        "source_blob_id": (
            _git(frozen_root, "rev-parse", f"{FROZEN_SOURCE_COMMIT}:{path}")
            .decode("ascii")
            .strip()
        ),
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
        raise ParityError(f"{context}: source runtime emitted illegal ticket: {value!r}")
    return sorted(cast(list[int], numbers))


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
            or "frozen wave-48 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-48 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-48 reference runtime changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-48 reference outputs changed")
    outputs = cast(dict[str, object], raw_outputs)
    if set(outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-48 reference outputs changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-48 ticket sequence changed")
        typed_raw_sequence = cast(list[object], raw_sequence)
        if len(typed_raw_sequence) != len(draws) - 1:
            raise ParityError("frozen wave-48 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(typed_raw_sequence):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-48 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-48 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-48 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def _load_prior_ledger(
    path: Path,
) -> tuple[list[str], list[str], dict[str, list[list[list[int]] | None]]]:
    parsed = json.loads(path.read_bytes())
    document = cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
    targets = document.get("target_draw_numbers")
    contexts = document.get("context_numbers_sha256_by_target")
    tickets = document.get("tickets_by_method")
    if not isinstance(targets, list) or not isinstance(contexts, list):
        raise ParityError("prior ledger identity changed")
    typed_targets = cast(list[object], targets)
    typed_contexts = cast(list[object], contexts)
    if (
        len(typed_targets) != 2148
        or len(typed_contexts) != 2148
        or not isinstance(tickets, dict)
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
    ):
        raise ParityError("prior ledger identity changed")
    return (
        cast(list[str], targets),
        cast(list[str], contexts),
        cast(dict[str, list[list[list[int]] | None]], tickets),
    )


def _alias_candidates(
    left_outputs: dict[str, list[list[list[int]] | None]],
    right_outputs: dict[str, list[list[list[int]] | None]],
    *,
    cross_ledger: bool,
) -> list[dict[str, object]]:
    pairs = (
        ((left, right) for left in left_outputs for right in right_outputs)
        if cross_ledger
        else combinations(left_outputs, 2)
    )
    candidates: list[dict[str, object]] = []
    for left, right in pairs:
        left_count = next((len(value) for value in left_outputs[left] if value is not None), 0)
        right_count = next((len(value) for value in right_outputs[right] if value is not None), 0)
        if left_count != right_count:
            continue
        overlapping = [
            (left_value, right_value)
            for left_value, right_value in zip(
                left_outputs[left],
                right_outputs[right],
                strict=True,
            )
            if left_value is not None and right_value is not None
        ]
        mismatch_count = sum(left_value != right_value for left_value, right_value in overlapping)
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


def verify_wave48_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the complete ledger and exact frozen-source parity proof."""

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
    ledger, parity = verify_wave48_parity(
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
