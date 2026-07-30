#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate wave-53 deterministic portfolios in the frozen legacy runtime."""

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
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_AST_FROZEN_FUNCTIONS"
)
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE53_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE53_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

ANALYSIS_METHOD_ID = "tools/analyze_prediction_115000019.py"
RGF_METHOD_ID = "tools/rgf_walkforward_validator.py"

SOURCE_SHA256_BY_METHOD = {
    ANALYSIS_METHOD_ID: (
        "021e1c5ede7bd1e89772d61744ea867616ee0af7f8fd441d92c3b4e0eb53d643"
    ),
    RGF_METHOD_ID: (
        "cab0d1127b625660dc68f237069150d6494bc06841b692bca347518431ae1efa"
    ),
}
DEPENDENCY_SHA256_BY_PATH: dict[str, str] = {}
MINIMUM_HISTORY_BY_METHOD = {
    ANALYSIS_METHOD_ID: 500,
    RGF_METHOD_ID: 200,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    ANALYSIS_METHOD_ID: "SOURCE_FOURIER_RHYTHM_DECLARED_WINDOW_500",
    RGF_METHOD_ID: "SOURCE_GMM_BURN_IN_200_WALK_FORWARD_BOUNDARY",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    ANALYSIS_METHOD_ID: 14,
    RGF_METHOD_ID: 6,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    ANALYSIS_METHOD_ID: (
        "P0_DEVIATION_ECHO_2BET",
        "TRIPLE_STRIKE_FOURIER_COLD_TAIL_3BET",
        "TS3_MARKOV_W30_4BET",
        "TS3_MARKOV_W30_FREQ_ORTHO_W200_5BET",
    ),
    RGF_METHOD_ID: (
        "FREQ_X_GAP_1BET",
        "FREQ_X_MARKOV_1BET",
        "GAP_X_MARKOV_1BET",
        "FREQ_ADD_GAP_1BET",
        "FREQ_ADD_MARKOV_1BET",
        "FREQ_ONLY_1BET",
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
import json
import os
import sys
from collections import Counter

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)

import numpy
import scipy
from scipy.fft import fft, fftfreq

draws = request["draws"]
minimums = request["minimum_history_by_method"]
analysis_id = "tools/analyze_prediction_115000019.py"
rgf_id = "tools/rgf_walkforward_validator.py"
outputs = {
    analysis_id: [None for _ in draws[1:]],
    rgf_id: [None for _ in draws[1:]],
}

analysis_path = os.path.join(root, analysis_id)
analysis_tree = ast.parse(
    open(analysis_path, encoding="utf-8").read(),
    analysis_path,
)
analysis_names = {
    "biglotto_p0_2bet",
    "fourier_rhythm_bet",
    "cold_numbers_bet",
    "tail_balance_bet",
    "generate_triple_strike",
    "markov_orthogonal_bet",
    "generate_ts3_markov4",
    "freq_orthogonal_bet",
    "generate_ts3_markov4_freqortho5",
}
analysis_nodes = [
    node
    for node in analysis_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name in analysis_names
]
if {node.name for node in analysis_nodes} != analysis_names:
    raise RuntimeError("frozen analysis strategy functions changed")
analysis_namespace = {
    "Counter": Counter,
    "MAX_NUM": 49,
    "PICK": 6,
    "fft": fft,
    "fftfreq": fftfreq,
    "np": numpy,
}
exec(
    compile(
        ast.Module(body=analysis_nodes, type_ignores=[]),
        analysis_path,
        "exec",
    ),
    analysis_namespace,
)
for target_index in range(minimums[analysis_id], len(draws)):
    history = draws[:target_index]
    outputs[analysis_id][target_index - 1] = [
        *analysis_namespace["biglotto_p0_2bet"](history),
        *analysis_namespace["generate_triple_strike"](history),
        *analysis_namespace["generate_ts3_markov4"](history),
        *analysis_namespace["generate_ts3_markov4_freqortho5"](history),
    ]

rgf_path = os.path.join(root, rgf_id)
rgf_tree = ast.parse(open(rgf_path, encoding="utf-8").read(), rgf_path)
rgf_names = {
    "compute_freq_score",
    "compute_gap_neg_score",
    "compute_markov_score",
    "top6_from_scores",
}
rgf_assignments = {"FREQ_WINDOW", "MARKOV_WINDOW", "FORMULAS"}
rgf_nodes = []
found_assignments = set()
for node in rgf_tree.body:
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in rgf_names
    ):
        rgf_nodes.append(node)
    elif isinstance(node, ast.Assign):
        names = {
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        if names & rgf_assignments:
            rgf_nodes.append(node)
            found_assignments.update(names & rgf_assignments)
if (
    {node.name for node in rgf_nodes if isinstance(node, ast.FunctionDef)}
    != rgf_names
    or found_assignments != rgf_assignments
):
    raise RuntimeError("frozen RGF strategy functions changed")
rgf_namespace = {"Counter": Counter, "np": numpy}
exec(
    compile(ast.Module(body=rgf_nodes, type_ignores=[]), rgf_path, "exec"),
    rgf_namespace,
)
for target_index in range(minimums[rgf_id], len(draws)):
    history = draws[:target_index]
    freq = rgf_namespace["compute_freq_score"](history, 49)
    gap = rgf_namespace["compute_gap_neg_score"](history, 49)
    markov = rgf_namespace["compute_markov_score"](history, 49)
    outputs[rgf_id][target_index - 1] = [
        sorted(
            rgf_namespace["top6_from_scores"](
                formula(freq, gap, markov),
                49,
            )
        )
        for formula in rgf_namespace["FORMULAS"].values()
    ]

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
            or "frozen wave-53 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-53 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-53 reference runtime changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-53 reference method set changed")
    typed_outputs = cast(dict[str, object], raw_outputs)
    if set(typed_outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-53 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = typed_outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-53 ticket sequence changed")
        candidates = cast(list[object], raw_sequence)
        if len(candidates) != len(draws) - 1:
            raise ParityError("frozen wave-53 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(candidates):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-53 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-53 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-53 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def verify_wave53_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the complete wave-53 ledger and frozen-source parity proof."""

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
            ANALYSIS_METHOD_ID: 0,
            RGF_METHOD_ID: (
                EXPECTED_OK_TARGET_COUNT_BY_METHOD[RGF_METHOD_ID]
                * NATIVE_TICKET_COUNT_BY_METHOD[RGF_METHOD_ID]
            ),
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
    ledger, parity = verify_wave53_parity(
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
