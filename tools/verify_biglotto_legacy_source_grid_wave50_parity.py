#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate wave-50 source-grid portfolios in the frozen legacy runtime."""

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
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE50_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_WAVE50_TICKET_LEDGER_V1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"

COVERING_METHOD_ID = "tools/covering_strategy_research.py"
EXHAUSTIVE_METHOD_ID = "tools/exhaustive_feature_sweep_v2.py"

SOURCE_SHA256_BY_METHOD = {
    COVERING_METHOD_ID: "214ecc206fc91280068db0f87476eec18d221800faa478a70d279712a63f8413",
    EXHAUSTIVE_METHOD_ID: "ff4096a9e7e59a4bf441d6c0ab4afa45a6471d71f532d26200fb810f5c5cb7bb",
}
DEPENDENCY_SHA256_BY_PATH = {
    "tools/biglotto_zonal_pruning.py": (
        "fad2b6700639bb495f31660626ac6ce1baee18d0fbbb630a40909677745ba8ed"
    ),
    "tools/chaos_entropy_selector.py": (
        "cd87065ee94e2ce20a77d541dbb7adf7112750828ad16ebee8c0a9de7663a4c8"
    ),
    "tools/power_fourier_rhythm.py": (
        "cb75e72e4c948466a23a432527ca9e5af40e8618c509154f54277ac860d62d59"
    ),
    "tools/predict_biglotto_apriori.py": (
        "cda690ae84c2324b5f7d160a68e0ba3cf65d6073ecfc5c28ef48402b07018e7b"
    ),
    "tools/strategy_leaderboard.py": (
        "5af2848b20597058819a49fb34a5fd5c3c9a2f26a91d89232ff8b177e510a334"
    ),
    "tools/verify_strategy_longterm.py": (
        "1d71057375535c060da0cccb02d6f9e60621351273b6ac8744b7d7775eb47ac3"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    COVERING_METHOD_ID: 649,
    EXHAUSTIVE_METHOD_ID: 1999,
}
MINIMUM_HISTORY_RATIONALE_BY_METHOD = {
    COVERING_METHOD_ID: "PINNED_LAST_1500_SOURCE_EVALUATION_BOUNDARY",
    EXHAUSTIVE_METHOD_ID: "PINNED_LAST_150_SOURCE_DEFAULT_EVALUATION_BOUNDARY",
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    COVERING_METHOD_ID: 40,
    EXHAUSTIVE_METHOD_ID: 12,
}
SOURCE_CONFIGURATION_MEMBERS_BY_METHOD = {
    COVERING_METHOD_ID: (
        "STATIC_ZERO_OVERLAP_5_SEED42",
        "STATIC_ANCHOR_K2_5_SEED42",
        "STATIC_ANCHOR_K3_5_SEED42",
        "STATIC_ANCHOR_K4_5_SEED42",
        "STATIC_RANDOM_INDEPENDENT_5_SEED42",
        "DYNAMIC_SIGNAL_GUIDED_TS3_M_FO_5",
        "DYNAMIC_COOCCURRENCE_GUIDED_5_W100_SEED42",
        "DYNAMIC_ZERO_OVERLAP_5_SEED_HISTORY_MOD10000",
    ),
    EXHAUSTIVE_METHOD_ID: (
        "STATISTICAL_FREQUENCY_W100_2BET",
        "STATISTICAL_FREQUENCY_W300_2BET",
        "HARMONIC_FFT_RHYTHM_W500_2BET",
        "SPATIAL_ZONAL_PRUNING_4ZONE_2BET",
        "CHAOS_ENTROPY_ADAPTIVE_KILL_2BET",
        "RELATIONAL_APRIORI_PAIRINGS_2BET",
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
import contextlib
import importlib.util
import io
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api"), os.path.join(root, "tools")]

import numpy
import scipy
from tools import strategy_leaderboard

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def lightweight_leaderboard_init(self, lottery_type="BIG_LOTTO", db_path=None):
    self.lottery_type = lottery_type
    self.max_num = 49 if lottery_type == "BIG_LOTTO" else 38

# ExhaustiveAnalyzer only calls strat_cluster_pivot; legacy constructor DB/model
# side effects do not participate in that selection logic.
strategy_leaderboard.StrategyLeaderboard.__init__ = lightweight_leaderboard_init

with contextlib.redirect_stdout(io.StringIO()):
    covering = load("tools/covering_strategy_research.py", "wave50_covering")
    exhaustive = load("tools/exhaustive_feature_sweep_v2.py", "wave50_exhaustive")

draws = request["draws"]
minimums = request["minimum_history_by_method"]
covering_id = "tools/covering_strategy_research.py"
exhaustive_id = "tools/exhaustive_feature_sweep_v2.py"
outputs = {
    covering_id: [None for _ in draws[1:]],
    exhaustive_id: [None for _ in draws[1:]],
}

static_rng = numpy.random.RandomState(42)
covering_configs = [
    covering.gen_zero_overlap(5, seed=42),
    covering.gen_anchor_k(5, 2, seed=42),
    covering.gen_anchor_k(5, 3, seed=42),
    covering.gen_anchor_k(5, 4, seed=42),
    [
        sorted(static_rng.choice(range(1, 50), size=6, replace=False).tolist())
        for _ in range(5)
    ],
]
for target_index in range(minimums[covering_id], len(draws)):
    portfolio = sum(covering_configs, [])
    outputs[covering_id][target_index - 1] = portfolio

dynamic_covering = [
    covering.gen_signal_guided,
    lambda history: covering.gen_cooccurrence_guided(
        history, 5, window=100, seed=42
    ),
    lambda history: covering.gen_zero_overlap(
        5, seed=len(history) % 10000
    ),
]
for function in dynamic_covering:
    for target_index in range(minimums[covering_id], len(draws)):
        outputs[covering_id][target_index - 1].extend(
            function(draws[:target_index])
        )

analyzer = exhaustive.ExhaustiveAnalyzer.__new__(exhaustive.ExhaustiveAnalyzer)
analyzer.lottery_type = "BIG_LOTTO"
analyzer.max_num = 49
exhaustive_configs = [
    analyzer.freq_strategy(100),
    analyzer.freq_strategy(300),
    analyzer.fft_strategy(500),
    analyzer.zonal_strategy(4),
    analyzer.chaos_strategy(),
    analyzer.apriori_strategy(),
]
with contextlib.redirect_stdout(io.StringIO()):
    for function in exhaustive_configs:
        numpy.random.seed(42)
        for target_index in range(minimums[exhaustive_id], len(draws)):
            outputs[exhaustive_id][target_index - 1] = (
                outputs[exhaustive_id][target_index - 1] or []
            )
            outputs[exhaustive_id][target_index - 1].extend(
                function(draws[:target_index], num_bets=2)
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
            or "frozen wave-50 reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen wave-50 reference emitted invalid JSON") from exc
    document = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen wave-50 reference runtime changed")
    raw_outputs = document.get("outputs")
    if not isinstance(raw_outputs, dict):
        raise ParityError("frozen wave-50 reference method set changed")
    typed_outputs = cast(dict[str, object], raw_outputs)
    if set(typed_outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen wave-50 reference method set changed")
    typed: dict[str, list[list[list[int]] | None]] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = typed_outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen wave-50 ticket sequence changed")
        candidates = cast(list[object], raw_sequence)
        if len(candidates) != len(draws) - 1:
            raise ParityError("frozen wave-50 ticket sequence changed")
        sequence: list[list[list[int]] | None] = []
        ok_count = 0
        for target_index, candidate in enumerate(candidates):
            if candidate is None:
                sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen wave-50 portfolio changed")
            tickets = [
                _validate_ticket(
                    ticket,
                    context=f"{method_id} target {target_index} ticket {ticket_index}",
                )
                for ticket_index, ticket in enumerate(cast(list[object], candidate))
            ]
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen wave-50 native count changed: {method_id}")
            sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen wave-50 eligible count changed: {method_id}")
        typed[method_id] = sequence
    return typed


def verify_wave50_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the complete wave-50 ledger and frozen-source parity proof."""

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
    ledger, parity = verify_wave50_parity(
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
