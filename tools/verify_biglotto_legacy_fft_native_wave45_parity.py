#!/usr/bin/env python3
"""Regenerate the wave-45 frozen FFT portfolios and alias proof."""

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

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_FFTPACK_POCKETFFT"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_PARITY_V1"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_TICKET_LEDGER_V1"
CONTEXT_DRAW_COUNT = 500

PP3_METHOD_ID = "tools/backtest_big_lotto_3bet.py"
TRIPLE_ORIGINAL_METHOD_ID = "tools/backtest_biglotto_triple_strike_original.py"
FCF_VS_TS3_METHOD_ID = "tools/backtest_fcf_vs_ts3.py"
TRIPLE_ALIAS_METHOD_ID = "tools/verify_biglotto_3bet_comparison.py"
MARKOV_VS_TRIPLE_METHOD_ID = "tools/verify_markov_vs_triple_2bet.py"

SOURCE_SHA256_BY_METHOD = {
    PP3_METHOD_ID: ("245f477b3e77422c33472ab7d093c40526d702cdffb0385e3c2f60bc50b691ba"),
    TRIPLE_ORIGINAL_METHOD_ID: ("4a8297a758b90b0a8697a889d2c9f1e9321ca2e1a5cac5322eb4e51d943e7977"),
    FCF_VS_TS3_METHOD_ID: ("efc61a5517309025e22b7e37186a6e23b72d3bca572f02f93af9748a238c91e8"),
    TRIPLE_ALIAS_METHOD_ID: ("03bb602d9a26fa431efa55ae4005f81556dbf715a3e42ad225a705f347c3c57a"),
    MARKOV_VS_TRIPLE_METHOD_ID: (
        "2094ee4bc361d87b70e49756966284bb1e996af830ae979d1fe598c75210200a"
    ),
}
MINIMUM_HISTORY_BY_METHOD = {
    PP3_METHOD_ID: 500,
    TRIPLE_ORIGINAL_METHOD_ID: 500,
    FCF_VS_TS3_METHOD_ID: 150,
    TRIPLE_ALIAS_METHOD_ID: 501,
    MARKOV_VS_TRIPLE_METHOD_ID: 501,
}
NATIVE_TICKET_COUNT_BY_METHOD = {
    PP3_METHOD_ID: 3,
    TRIPLE_ORIGINAL_METHOD_ID: 3,
    FCF_VS_TS3_METHOD_ID: 6,
    TRIPLE_ALIAS_METHOD_ID: 3,
    MARKOV_VS_TRIPLE_METHOD_ID: 4,
}
EXPECTED_OK_TARGET_COUNT_BY_METHOD = {
    PP3_METHOD_ID: 1649,
    TRIPLE_ORIGINAL_METHOD_ID: 1649,
    FCF_VS_TS3_METHOD_ID: 1999,
    TRIPLE_ALIAS_METHOD_ID: 1648,
    MARKOV_VS_TRIPLE_METHOD_ID: 1648,
}

_REFERENCE_SCRIPT = r"""
import importlib.util
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api")]

import numpy
import scipy

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pp3 = load("tools/backtest_big_lotto_3bet.py", "wave45_pp3")
original = load(
    "tools/backtest_biglotto_triple_strike_original.py",
    "wave45_triple_original",
)
fcf = load("tools/backtest_fcf_vs_ts3.py", "wave45_fcf_vs_ts3")
alias = load(
    "tools/verify_biglotto_3bet_comparison.py",
    "wave45_triple_alias",
)
markov = load(
    "tools/verify_markov_vs_triple_2bet.py",
    "wave45_markov_vs_triple",
)

draws = request["draws"]
start_index = request["start_index"]
minimums = request["minimum_history_by_method"]
method_ids = request["method_ids"]
outputs = {method_id: [] for method_id in method_ids}

for target_index in range(start_index, len(draws)):
    history = draws[:target_index]

    method_id = "tools/backtest_big_lotto_3bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else pp3.generate_big_lotto_3bet(history)
    )

    method_id = "tools/backtest_biglotto_triple_strike_original.py"
    if target_index < minimums[method_id]:
        outputs[method_id].append(None)
    else:
        b1 = original.fourier_rhythm_bet(history)
        b2 = original.cold_numbers_bet(history, exclude=set(b1))
        b3 = original.tail_balance_bet(
            history,
            exclude=set(b1) | set(b2),
        )
        outputs[method_id].append([b1, b2, b3])

    method_id = "tools/backtest_fcf_vs_ts3.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else fcf.generate_ts3(history) + fcf.generate_fcf(history)
    )

    method_id = "tools/verify_biglotto_3bet_comparison.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else alias.triple_strike_biglotto(history)
    )

    method_id = "tools/verify_markov_vs_triple_2bet.py"
    outputs[method_id].append(
        None if target_index < minimums[method_id]
        else (
            markov.markov_2bet(history)
            + markov.triple_strike_2bet(history)
        )
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
            completed.stderr.decode("utf-8", errors="replace").strip() or "frozen Git query failed"
        )
    return completed.stdout


def _source_artifact(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    method_id: str,
) -> dict[str, str]:
    expected_sha256 = SOURCE_SHA256_BY_METHOD[method_id]
    git_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    extracted_raw = frozen_source_directory.joinpath(method_id).read_bytes()
    if git_raw != extracted_raw or hashlib.sha256(git_raw).hexdigest() != expected_sha256:
        raise ParityError(f"frozen source identity changed: {method_id}")
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        .decode("ascii")
        .strip()
    )
    return {
        "path": method_id,
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
) -> tuple[
    dict[str, list[list[list[int]] | None]],
    dict[str, int],
]:
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
                "start_index": min(MINIMUM_HISTORY_BY_METHOD.values()),
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
            or "frozen FFT reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError("frozen FFT reference emitted invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen FFT reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen FFT reference runtime changed")
    outputs_raw = document.get("outputs")
    if not isinstance(outputs_raw, dict):
        raise ParityError("frozen FFT reference method outputs changed")
    outputs = cast(dict[str, object], outputs_raw)
    if set(outputs) != set(SOURCE_SHA256_BY_METHOD):
        raise ParityError("frozen FFT reference method set changed")
    expected_sequence_length = len(draws) - min(MINIMUM_HISTORY_BY_METHOD.values())
    typed: dict[str, list[list[list[int]] | None]] = {}
    intra_ticket_canonicalization_count: dict[str, int] = {}
    for method_id, expected_ticket_count in NATIVE_TICKET_COUNT_BY_METHOD.items():
        raw_sequence = outputs[method_id]
        if not isinstance(raw_sequence, list):
            raise ParityError("frozen FFT ticket sequence changed")
        sequence = cast(list[object], raw_sequence)
        if len(sequence) != expected_sequence_length:
            raise ParityError("frozen FFT target sequence changed")
        typed_sequence: list[list[list[int]] | None] = []
        ok_count = 0
        canonicalization_count = 0
        for candidate in sequence:
            if candidate is None:
                typed_sequence.append(None)
                continue
            if not isinstance(candidate, list):
                raise ParityError("frozen FFT portfolio changed")
            raw_tickets = cast(list[object], candidate)
            tickets = [
                _validate_ticket(
                    ticket,
                    context=(f"{method_id} sequence {len(typed_sequence)} ticket {ticket_index}"),
                )
                for ticket_index, ticket in enumerate(
                    raw_tickets,
                    start=1,
                )
            ]
            canonicalization_count += sum(
                isinstance(ticket, list) and ticket != sorted(cast(list[Any], ticket))
                for ticket in raw_tickets
            )
            if len(tickets) != expected_ticket_count:
                raise ParityError(f"frozen FFT native count changed: {method_id}")
            typed_sequence.append(tickets)
            ok_count += 1
        if ok_count != EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id]:
            raise ParityError(f"frozen FFT eligible count changed: {method_id}")
        typed[method_id] = typed_sequence
        intra_ticket_canonicalization_count[method_id] = canonicalization_count
    return typed, intra_ticket_canonicalization_count


def verify_wave45_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return a complete ledger and its frozen-source parity proof."""

    if expected_database_sha256 != PINNED_DATASET_SHA256:
        raise ParityError("wave-45 parity requires the pinned full dataset")
    source_artifacts = [
        _source_artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            method_id=method_id,
        )
        for method_id in SOURCE_SHA256_BY_METHOD
    ]
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
    outputs, canonicalization_counts = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    start_index = min(MINIMUM_HISTORY_BY_METHOD.values())
    target_draw_numbers = [draw.draw_number for draw in pinned.draws[start_index:]]
    context_numbers_sha256 = [
        hashlib.sha256(
            json.dumps(
                [
                    list(draw.numbers)
                    for draw in pinned.draws[
                        max(0, target_index - CONTEXT_DRAW_COUNT) : target_index
                    ]
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for target_index in range(start_index, len(pinned.draws))
    ]
    original = outputs[TRIPLE_ORIGINAL_METHOD_ID]
    alias = outputs[TRIPLE_ALIAS_METHOD_ID]
    alias_mismatches = [
        target_draw_numbers[offset]
        for offset, (original_tickets, alias_tickets) in enumerate(
            zip(original, alias, strict=True)
        )
        if alias_tickets is not None and original_tickets != alias_tickets
    ]
    if alias_mismatches:
        raise ParityError("Triple Strike alias output parity failed")
    sequence_sha256_by_method = {
        method_id: hashlib.sha256(_canonical_bytes(sequence)).hexdigest()
        for method_id, sequence in outputs.items()
    }
    ledger: dict[str, object] = {
        "context_draw_count": CONTEXT_DRAW_COUNT,
        "context_numbers_sha256_by_target": context_numbers_sha256,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "minimum_history_by_method": MINIMUM_HISTORY_BY_METHOD,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(_canonical_bytes(ledger)).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "alias_case_count": EXPECTED_OK_TARGET_COUNT_BY_METHOD[TRIPLE_ALIAS_METHOD_ID],
        "alias_mismatch_count": 0,
        "alias_source_method": TRIPLE_ALIAS_METHOD_ID,
        "alias_target_method": TRIPLE_ORIGINAL_METHOD_ID,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": sum(
            EXPECTED_OK_TARGET_COUNT_BY_METHOD[method_id] * NATIVE_TICKET_COUNT_BY_METHOD[method_id]
            for method_id in SOURCE_SHA256_BY_METHOD
        ),
        "ok_target_count_by_method": EXPECTED_OK_TARGET_COUNT_BY_METHOD,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "intra_ticket_canonicalization_count_by_method": (canonicalization_counts),
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
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, parity = verify_wave45_parity(
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
                "alias_case_count": parity["alias_case_count"],
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
