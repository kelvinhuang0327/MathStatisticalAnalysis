#!/usr/bin/env python3
"""Regenerate wave-47 deterministic portfolios in the frozen source runtime."""

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
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE47_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE47_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

EDGE_SPLICER_METHOD_ID = "tools/edge_splicer.py"
EDGE_SPLICER_5BET_METHOD_ID = "tools/edge_splicer_5bet.py"
EDGE_SPLICER_V2_METHOD_ID = "tools/edge_splicer_v2.py"
CONCENTRATOR_METHOD_ID = "tools/evaluate_concentrator.py"
ORTHOGONAL_2_3_METHOD_ID = "tools/generate_2_3_bets.py"
STABILITY_METHOD_ID = "tools/stability_coverage_study.py"
STANDARD_TS3_METHOD_ID = "tools/standard_ts3_5bet.py"
QUICK_PREDICT_METHOD_ID = "tools/quick_predict.py"

SOURCE_SHA256_BY_METHOD = {
    EDGE_SPLICER_METHOD_ID: ("04d9e8bbfe76f16be95e0a1f4e016913fb29c69add18313eeaca9a378d51c58c"),
    EDGE_SPLICER_5BET_METHOD_ID: (
        "da1d1eed4d966323a9570a75ea334983e912bf90ace978f6ad112db53951d479"
    ),
    EDGE_SPLICER_V2_METHOD_ID: ("6b6e9d64da1253762c5fa22eb8a4f815bf4c3e058b952c2a05a2a9654782bf00"),
    CONCENTRATOR_METHOD_ID: ("d732e4dd594c9f19aff5dea2292711d33a4bb6e7c3acd0a4ecd9fc5aba302970"),
    ORTHOGONAL_2_3_METHOD_ID: ("f8853b95f3c53bd25e0af0a6ddd5060046ac457faeba523d8ff68eff25af1000"),
    STABILITY_METHOD_ID: ("71ce29834518d6d3af3375cd4dd2452d1b67da95b43f807a194cc1bd0e8013ba"),
    STANDARD_TS3_METHOD_ID: ("527fed00a7c4d47bbd286dfce905ca278c471cacaadf4e8e93ab3f693425db74"),
    QUICK_PREDICT_METHOD_ID: ("86259fc99c70862b8d7730280bdccf4f37c24d9a951d67501ff188a8af3c3344"),
}
DEPENDENCY_SHA256_BY_PATH = {
    "tools/evolving_strategy_engine/strategy_base.py": (
        "b9224ce1634482f751223752c7308233a8fd836b9e133facb95458edc85238ea"
    ),
    "tools/evolving_strategy_engine/data_loader.py": (
        "9a4ba5fd53737cbb7b2c88713c35c3fe4b8c3e7c21c8f2836c5b76a1e9784931"
    ),
    "tools/backtest_biglotto_markov_4bet.py": (
        "aefb54eb345bf38fbeb1526959c12a3585a970325316dfbc2c6a7bb440b5ec6a"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    EDGE_SPLICER_METHOD_ID: 649,
    EDGE_SPLICER_5BET_METHOD_ID: 649,
    EDGE_SPLICER_V2_METHOD_ID: 649,
    CONCENTRATOR_METHOD_ID: 649,
    ORTHOGONAL_2_3_METHOD_ID: 1,
    STABILITY_METHOD_ID: 500,
    STANDARD_TS3_METHOD_ID: 649,
    QUICK_PREDICT_METHOD_ID: 50,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    EDGE_SPLICER_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    EDGE_SPLICER_5BET_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    EDGE_SPLICER_V2_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    CONCENTRATOR_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    ORTHOGONAL_2_3_METHOD_ID: "SOURCE_GENERATOR_DEFINED_WITH_ONE_PRIOR_DRAW",
    STABILITY_METHOD_ID: "SOURCE_MIN_BUFFER_500",
    STANDARD_TS3_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    QUICK_PREDICT_METHOD_ID: "SOURCE_CLI_REQUIRES_50_HISTORY_DRAWS",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    EDGE_SPLICER_METHOD_ID: 5,
    EDGE_SPLICER_5BET_METHOD_ID: 5,
    EDGE_SPLICER_V2_METHOD_ID: 3,
    CONCENTRATOR_METHOD_ID: 2,
    ORTHOGONAL_2_3_METHOD_ID: 5,
    STABILITY_METHOD_ID: 5,
    STANDARD_TS3_METHOD_ID: 5,
    QUICK_PREDICT_METHOD_ID: 5,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    EDGE_SPLICER_METHOD_ID: (
        "CUSTOM_ORTHOGONAL_2BET",
        "CUSTOM_ORTHOGONAL_3BET",
    ),
    EDGE_SPLICER_5BET_METHOD_ID: ("FIVE_ATOMIC_SIGNAL_ORTHOGONAL_MATRIX",),
    EDGE_SPLICER_V2_METHOD_ID: ("TRI_AXIS_ORTHOGONAL_MATRIX",),
    CONCENTRATOR_METHOD_ID: ("CO_OCCURRENCE_CONCENTRATED_2BET",),
    ORTHOGONAL_2_3_METHOD_ID: (
        "ORTHOGONAL_SNAKE_DRAFT_2BET",
        "ORTHOGONAL_SNAKE_DRAFT_3BET",
    ),
    STABILITY_METHOD_ID: ("BIG_LOTTO_TS3_MARKOV_FREQ_ORTHO_5BET",),
    STANDARD_TS3_METHOD_ID: ("ORIGINAL_TS3_MARKOV_FREQ_ORTHO_5BET",),
    QUICK_PREDICT_METHOD_ID: ("DEFAULT_BIG_LOTTO_5BET_ORTHOGONAL",),
}
SOURCE_CONFIGURATION_COUNT_BY_METHOD = {
    method_id: len(members) for method_id, members in SOURCE_CONFIGURATION_MEMBERS_BY_METHOD.items()
}
EXPECTED_OK_TARGET_COUNT_BY_METHOD = {
    method_id: 2149 - minimum for method_id, minimum in MINIMUM_HISTORY_BY_METHOD.items()
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

edge = load("tools/edge_splicer.py", "wave47_edge")
edge5 = load("tools/edge_splicer_5bet.py", "wave47_edge5")
edgev2 = load("tools/edge_splicer_v2.py", "wave47_edgev2")
concentrator = load("tools/evaluate_concentrator.py", "wave47_concentrator")
orthogonal23 = load("tools/generate_2_3_bets.py", "wave47_orthogonal23")
stability = load("tools/stability_coverage_study.py", "wave47_stability")
standard = load("tools/standard_ts3_5bet.py", "wave47_standard")
quick = load("tools/quick_predict.py", "wave47_quick")

draws = request["draws"]
minimums = request["minimum_history_by_method"]
method_ids = request["method_ids"]
outputs = {method_id: [] for method_id in method_ids}

for target_index in range(1, len(draws)):
    history = draws[:target_index]
    raw = numpy.asarray([item["numbers"] for item in history], dtype=numpy.int32)

    method_id = "tools/edge_splicer.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else edge.generate_custom_bets(raw, 2)[0] + edge.generate_custom_bets(raw, 3)[0]
    )

    method_id = "tools/edge_splicer_5bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else edge5.generate_5_bet_matrix(raw)[0]
    )

    method_id = "tools/edge_splicer_v2.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else edgev2.generate_tri_axis_bets(raw)[0]
    )

    method_id = "tools/evaluate_concentrator.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else concentrator.generate_concentrated_2bet(raw)
    )

    method_id = "tools/generate_2_3_bets.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            orthogonal23.generate_orthogonal_bets(raw, 2)[1]
            + orthogonal23.generate_orthogonal_bets(raw, 3)[1]
        )
    )

    method_id = "tools/stability_coverage_study.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else stability.generate_biglotto_5bet(history)
    )

    method_id = "tools/standard_ts3_5bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else standard.gen_original(raw)
    )

    method_id = "tools/quick_predict.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else [item["numbers"] for item in quick.biglotto_5bet_orthogonal(history)]
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
            completed.stderr.decode("utf-8", errors="replace").strip() or "frozen Git query failed"
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
    blob_id = (
        _git(frozen_root, "rev-parse", f"{FROZEN_SOURCE_COMMIT}:{path}").decode("ascii").strip()
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
            or "frozen wave-47 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-47 reference emitted invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen wave-47 reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-47 reference runtime changed")
    outputs_raw = document.get("outputs")
    if not isinstance(outputs_raw, dict):
        raise ParityError("frozen wave-47 reference outputs changed")
    outputs = cast(dict[str, object], outputs_raw)
    if set(outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-47 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-47 ticket sequence changed")
        sequence = cast(list[object], raw_sequence)
        if len(sequence) != len(draws) - 1:
            raise ParityError("frozen wave-47 target sequence changed")
        typed_sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for candidate_index, candidate in enumerate(sequence):
            if candidate is None:
                typed_sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-47 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} sequence {candidate_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(
                    cast(list[object], candidate),
                    start=1,
                )
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-47 native count changed: {method_id}")
            typed_sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-47 eligible count changed: {method_id}")
        typed[method_id] = typed_sequence
    return typed


def _alias_candidates(
    left_outputs: dict[str, list[list[list[int]] | None]],
    right_outputs: dict[str, list[list[list[int]] | None]],
    *,
    cross_ledger: bool,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    pairs = (
        ((left, right) for left in left_outputs for right in right_outputs)
        if cross_ledger
        else combinations(left_outputs, 2)
    )
    for left, right in pairs:
        left_count = next(
            (len(value) for value in left_outputs[left] if value is not None),
            0,
        )
        right_count = next(
            (len(value) for value in right_outputs[right] if value is not None),
            0,
        )
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


def _load_prior_outputs(
    path: Path | None,
) -> dict[str, list[list[list[int]] | None]]:
    if path is None:
        return {}
    parsed = json.loads(path.read_bytes())
    if not isinstance(parsed, dict):
        raise ParityError("prior ledger is not an object")
    document = cast(dict[str, object], parsed)
    tickets = document.get("tickets_by_method")
    if not isinstance(tickets, dict):
        raise ParityError("prior ledger has no tickets_by_method")
    target_draw_numbers = document.get("target_draw_numbers")
    typed_target_draw_numbers = (
        cast(list[object], target_draw_numbers)
        if isinstance(target_draw_numbers, list)
        else []
    )
    if len(typed_target_draw_numbers) != 2148:
        raise ParityError("prior ledger target sequence changed")
    return cast(dict[str, list[list[list[int]] | None]], tickets)


def _validate_pinned_logical_anchor(
    *,
    path: Path | None,
    target_draw_numbers: list[str],
    context_numbers_sha256: list[str],
) -> None:
    if path is None:
        raise ParityError(
            "non-identical physical regeneration database requires "
            "the checksummed pinned logical anchor ledger"
        )
    parsed = json.loads(path.read_bytes())
    document = cast(dict[str, object], parsed) if isinstance(parsed, dict) else {}
    if (
        not isinstance(parsed, dict)
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("target_draw_numbers") != target_draw_numbers
        or document.get("context_numbers_sha256_by_target")
        != context_numbers_sha256
    ):
        raise ParityError("regeneration database does not match the pinned logical history")


def verify_wave47_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return a complete ledger and its frozen-source parity proof."""

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
    outputs = _reference_outputs(
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
    if expected_database_sha256 != PINNED_DATASET_SHA256:
        _validate_pinned_logical_anchor(
            path=prior_ledger,
            target_draw_numbers=target_draw_numbers,
            context_numbers_sha256=context_numbers_sha256,
        )
    ledger: dict[str, object] = {
        "context_numbers_sha256_by_target": context_numbers_sha256,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "minimum_history_by_method": MINIMUM_HISTORY_BY_METHOD,
        "minimum_history_rationale_by_method": (MINIMUM_HISTORY_RATIONALE_BY_METHOD),
        "source_configuration_count_by_method": (SOURCE_CONFIGURATION_COUNT_BY_METHOD),
        "source_configuration_members_by_method": (SOURCE_CONFIGURATION_MEMBERS_BY_METHOD),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(_canonical_bytes(ledger)).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    exact_alias_candidates = _alias_candidates(
        outputs,
        outputs,
        cross_ledger=False,
    )
    prior_outputs = _load_prior_outputs(prior_ledger)
    cross_wave_alias_candidates = (
        _alias_candidates(
            outputs,
            prior_outputs,
            cross_ledger=True,
        )
        if prior_outputs
        else []
    )
    parity: dict[str, object] = {
        "cross_wave_exact_alias_candidates": cross_wave_alias_candidates,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "exact_alias_candidates": exact_alias_candidates,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "intra_ticket_canonicalization_count_by_method": {
            method_id: 0 for method_id in SOURCE_SHA256_BY_METHOD
        },
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": sum(
            EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id] * NATIVE_TICKET_COUNT_BY_METHOD[method_id]
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
    parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument(
        "--reference-python",
        default=Path("/usr/bin/python3"),
        type=Path,
    )
    parser.add_argument("--prior-ledger", type=Path)
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, parity = verify_wave47_parity(
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
                    cast(
                        list[object],
                        parity["cross_wave_exact_alias_candidates"],
                    )
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
