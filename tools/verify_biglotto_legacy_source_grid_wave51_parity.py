#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate wave-51 seeded portfolios in the frozen legacy runtime."""

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
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_MT19937"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE51_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE51_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

CLUSTER_METHOD_ID = "tools/optimize_biglotto_cluster.py"
DEVIATION_METHOD_ID = "tools/optimize_deviation_extreme_generic.py"

SOURCE_SHA256_BY_METHOD = {
    CLUSTER_METHOD_ID: "b2a833918f9558a577c18a297e920d1eb9f50bb926795821bb65baa83d8ea675",
    DEVIATION_METHOD_ID: (
        "87e19bb3514af177077869bd8f5ca8ea0aed273584b4af8e577fa7fac11cdc31"
    ),
}
DEPENDENCY_SHA256_BY_PATH = {
    "lottery_api/models/unified_predictor.py": (
        "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
    ),
    "tools/backtest_cluster_pivot_biglotto.py": (
        "b28957a6433e2e42ed7307e524a41be1e04871b2c14a52fd36d15124c4cb02d3"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    CLUSTER_METHOD_ID: 1999,
    DEVIATION_METHOD_ID: 1999,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    CLUSTER_METHOD_ID: "PINNED_LAST_150_SOURCE_EVALUATION_BOUNDARY",
    DEVIATION_METHOD_ID: "PINNED_LAST_150_SOURCE_EVALUATION_BOUNDARY",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    CLUSTER_METHOD_ID: 4,
    DEVIATION_METHOD_ID: 1,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    CLUSTER_METHOD_ID: (
        "BIG_LOTTO_4BET_DYNAMIC_CLUSTER_COLD5_FILTER_GLOBAL_SEED42",
    ),
    DEVIATION_METHOD_ID: (
        "BIG_LOTTO_1BET_DEVIATION_EXTREME_500_CANDIDATES_GLOBAL_SEED42",
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
import importlib.util
import json
import os
import random
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

cluster = load("tools/optimize_biglotto_cluster.py", "wave51_cluster")
deviation = load(
    "tools/optimize_deviation_extreme_generic.py",
    "wave51_deviation",
)

draws = request["draws"]
minimums = request["minimum_history_by_method"]
cluster_id = "tools/optimize_biglotto_cluster.py"
deviation_id = "tools/optimize_deviation_extreme_generic.py"
outputs = {
    cluster_id: [None for _ in draws[1:]],
    deviation_id: [None for _ in draws[1:]],
}

numpy.random.seed(42)
random.seed(42)
for target_index in range(minimums[cluster_id], len(draws)):
    history = draws[:target_index]
    recent_nums = [
        number for draw in history[-50:] for number in draw["numbers"]
    ]
    frequencies = cluster.Counter(recent_nums)
    negative_pool = set(
        sorted(range(1, 50), key=lambda number: frequencies.get(number, 0))[:5]
    )
    tickets = cluster.cluster_pivot_optimized(
        history,
        max_num=49,
        num_bets=4,
        negative_pool=negative_pool,
    )
    outputs[cluster_id][target_index - 1] = [
        [int(number) for number in ticket] for ticket in tickets
    ]

numpy.random.seed(42)
random.seed(42)
predictor = deviation.DeviationExtremePredictor.__new__(
    deviation.DeviationExtremePredictor
)
rules = {
    "lotteryType": "BIG_LOTTO",
    "maxNumber": 49,
    "minNumber": 1,
    "pickCount": 6,
}
newest_first = list(reversed(draws))
for source_index in range(149, -1, -1):
    target_index = len(draws) - 1 - source_index
    result = predictor.predict(newest_first[source_index + 1:], rules)
    outputs[deviation_id][target_index - 1] = [
        [int(number) for number in result["numbers"]]
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
            or "frozen wave-51 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-51 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-51 reference runtime changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-51 reference method set changed")
    typed_outputs = cast(dict[str, object], raw_outputs)
    if set(typed_outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-51 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = typed_outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-51 ticket sequence changed")
        candidates = cast(list[object], raw_sequence)
        if len(candidates) != len(draws) - 1:
            raise ParityError("frozen wave-51 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(candidates):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-51 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-51 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-51 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def verify_wave51_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the complete wave-51 ledger and frozen-source parity proof."""

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
            role=(
                "DECLARED_BUT_SELECTION_UNUSED_DEPENDENCY"
                if path.endswith("unified_predictor.py")
                else "SELECTION_LOGIC_DEPENDENCY"
            ),
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
    ledger, parity = verify_wave51_parity(
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
