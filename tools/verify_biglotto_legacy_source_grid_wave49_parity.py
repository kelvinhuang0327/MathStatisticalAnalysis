#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate wave-49 deterministic portfolios in the frozen source runtime."""

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
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE49_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE49_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

AUTO_DISCOVERY_METHOD_ID = "tools/auto_discovery_biglotto.py"
EVALUATE_COMBINATIONS_METHOD_ID = "tools/evaluate_combinations.py"
FOURIER_RHYTHM_METHOD_ID = "tools/power_fourier_rhythm.py"

SOURCE_SHA256_BY_METHOD = {
    AUTO_DISCOVERY_METHOD_ID: ("06bcb164db844857927366a5e0216387a56f490ae689c8114608fec84d5a4765"),
    EVALUATE_COMBINATIONS_METHOD_ID: (
        "d49d0787d0c6fb9407024111d339cf76c4b165dc90d0713a0ac589929f9371a0"
    ),
    FOURIER_RHYTHM_METHOD_ID: ("cb75e72e4c948466a23a432527ca9e5af40e8618c509154f54277ac860d62d59"),
}
DEPENDENCY_SHA256_BY_PATH = {
    "tools/evolving_strategy_engine/strategy_base.py": (
        "b9224ce1634482f751223752c7308233a8fd836b9e133facb95458edc85238ea"
    ),
    "tools/strategy_leaderboard.py": (
        "5af2848b20597058819a49fb34a5fd5c3c9a2f26a91d89232ff8b177e510a334"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    AUTO_DISCOVERY_METHOD_ID: 649,
    EVALUATE_COMBINATIONS_METHOD_ID: 649,
    FOURIER_RHYTHM_METHOD_ID: 500,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    AUTO_DISCOVERY_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    EVALUATE_COMBINATIONS_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    FOURIER_RHYTHM_METHOD_ID: "SOURCE_FOURIER_WINDOW_500",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    AUTO_DISCOVERY_METHOD_ID: 54,
    EVALUATE_COMBINATIONS_METHOD_ID: 14,
    FOURIER_RHYTHM_METHOD_ID: 2,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    AUTO_DISCOVERY_METHOD_ID: tuple(
        sorted(
            (
                "A1_cooc_pairs_w30",
                "A1_cooc_pairs_w50",
                "A1_cooc_pairs_w100",
                "A1_cooc_pairs_w200",
                "A2_cooc_trans_w30",
                "A2_cooc_trans_w50",
                "A2_cooc_trans_w100",
                "A3_cooc_anti_w50",
                "A3_cooc_anti_w100",
                "A3_cooc_anti_w200",
                "A4_cooc_trip_w50",
                "A4_cooc_trip_w100",
                "A5_cooc_cond_w30",
                "A5_cooc_cond_w50",
                "A5_cooc_cond_w100",
                "B1_struct_tmpl_w100",
                "B1_struct_tmpl_w200",
                "B1_struct_tmpl_w500",
                "B2_struct_sum_w30",
                "B2_struct_sum_w50",
                "B2_struct_sum_w100",
                "B3_struct_oe_w50",
                "B3_struct_oe_w100",
                "B3_struct_oe_w200",
                "B4_struct_gap_w50",
                "B4_struct_gap_w100",
                "C1_cond_entropy_w50",
                "C1_cond_entropy_w100",
                "C1_cond_entropy_w200",
                "C2_mutual_info_w50",
                "C2_mutual_info_w100",
                "C3_surprise_w50",
                "C3_surprise_w100",
                "D1_neg_elim_w30",
                "D1_neg_elim_w50",
                "D1_neg_elim_w100",
                "D2_neg_overdue",
                "D3_neg_consensus_w20",
                "D3_neg_consensus_w30",
                "D3_neg_consensus_w50",
                "E1_zone_trans_w50",
                "E1_zone_trans_w100",
                "E1_zone_trans_w200",
                "E2_zone_consec_w30",
                "E2_zone_consec_w50",
                "E2_zone_consec_w100",
                "F1_graph_degree_w50",
                "F1_graph_degree_w100",
                "F1_graph_degree_w200",
                "F2_graph_bridge_w50",
                "F2_graph_bridge_w100",
                "F3_graph_pagerank_w50",
                "F3_graph_pagerank_w100",
                "F3_graph_pagerank_w200",
            )
        )
    ),
    EVALUATE_COMBINATIONS_METHOD_ID: (
        "SIGNAL_PREFIX_2BET",
        "SIGNAL_PREFIX_3BET",
        "SIGNAL_PREFIX_4BET",
        "SIGNAL_PREFIX_5BET",
    ),
    FOURIER_RHYTHM_METHOD_ID: ("BIG_LOTTO_DEFAULT_2BET_FOURIER_WINDOW_500",),
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

auto = load("tools/auto_discovery_biglotto.py", "wave49_auto")
evaluate = load("tools/evaluate_combinations.py", "wave49_evaluate")
fourier = load("tools/power_fourier_rhythm.py", "wave49_fourier")

draws = request["draws"]
minimums = request["minimum_history_by_method"]
method_ids = request["method_ids"]
outputs = {method_id: [] for method_id in method_ids}
auto_methods = sorted(auto.build_methods().items())

for target_index in range(1, len(draws)):
    history = draws[:target_index]
    raw = numpy.asarray([item["numbers"] for item in history], dtype=numpy.int32)

    method_id = "tools/auto_discovery_biglotto.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else [function(history) for _, function in auto_methods]
    )

    method_id = "tools/evaluate_combinations.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else sum((evaluate.generate_bets(raw, n_bets)[0] for n_bets in range(2, 6)), [])
    )

    method_id = "tools/power_fourier_rhythm.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else fourier.fourier_rhythm_predict(history, n_bets=2, window=500)
    )

json.dump(
    {
        "auto_method_names": [name for name, _ in auto_methods],
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
            or "frozen wave-49 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-49 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
        or document.get("auto_method_names")
        != sorted(SOURCE_CONFIGURATION_MEMBERS_BY_METHOD[AUTO_DISCOVERY_METHOD_ID])
    ):
        raise ParityError("frozen wave-49 reference runtime or configuration order changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-49 reference outputs changed")
    outputs = cast(dict[str, object], raw_outputs)
    if set(outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-49 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-49 ticket sequence changed")
        candidates = cast(list[object], raw_sequence)
        if len(candidates) != len(draws) - 1:
            raise ParityError("frozen wave-49 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(candidates):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-49 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-49 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-49 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def verify_wave49_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
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
    ledger, parity = verify_wave49_parity(
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
