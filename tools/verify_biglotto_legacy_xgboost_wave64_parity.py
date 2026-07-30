#!/usr/bin/env python3
"""Regenerate every wave-64 XGBoost ticket from the frozen source."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
METHOD_ID = "lottery_api/models/xgboost_model.py"
SOURCE_SHA256 = (
    "38c72a70c627285dab2b55163b387b3ed8ab6bd9820c10d7daed0dce777f1c01"
)
SOURCE_BLOB_ID = "331b97562b593c061937ad9afac79fc5b8d88152"
SOURCE_BYTE_SIZE = 8389
HISTORY_INPUT_FILE_SHA256 = (
    "e501c2e1b0a5c610bae3822a2784a72860e2c549daadb37c344de61d16129493"
)
HISTORY_INPUT_CANONICAL_SHA256 = (
    "155766ddc1f7581392d91fc8f5e79a433f6e245a9feefb5cb059b8d2594af7c9"
)
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_XGBOOST_WAVE64_TICKET_LEDGER_V1"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_XGBOOST_WAVE64_PARITY_V1"
CAUSAL_PROTOCOL = (
    "FROZEN_XGBOOST_PREDICT_STRICT_PREFIX_RECENT1000_"
    "XGBOOST_2_0_2_SKLEARN_1_3_2_V1"
)
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_STRICTLY_EARLIER_DRAWS_WITH_SOURCE_RECENT1000_LIMIT"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_PANDAS_2_1_3_"
    "SKLEARN_1_3_2_XGBOOST_2_0_2"
)
CLOSED_REASON = "TRAINING_DATA_INSUFFICIENT_LT_15_HISTORY_DRAWS"
THREAD_PARITY_INDICES = (15, 50, 100, 999, 2148)

_REFERENCE_SCRIPT = r"""
import asyncio
import importlib.util
import json
import logging
import sys
import types

request = json.load(sys.stdin)
root_name = "frozen_lottery_api"
models_name = root_name + ".models"
root = types.ModuleType(root_name)
root.__path__ = []
models = types.ModuleType(models_name)
models.__path__ = []
unified = types.ModuleType(models_name + ".unified_predictor")
unified.log_data_range = lambda method, history: None
unified.get_data_range_info = lambda history: {}
sys.modules[root_name] = root
sys.modules[models_name] = models
sys.modules[unified.__name__] = unified

path = request["source_path"]
spec = importlib.util.spec_from_file_location(
    models_name + ".xgboost_model",
    path,
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

import numpy
import pandas
import sklearn
import xgboost

logging.disable(logging.CRITICAL)
draws = request["draws"]
rules = {
    "hasSpecialNumber": False,
    "maxNumber": 49,
    "minNumber": 1,
    "pickCount": 6,
}
rows = []
for target_index in request["indices"]:
    history = draws[:target_index]
    try:
        result = asyncio.run(
            module.XGBoostPredictor().predict(history, rules)
        )
    except ValueError as exc:
        if str(exc) != "訓練數據不足":
            raise
        rows.append(
            {
                "closed_reason": request["closed_reason"],
                "status": "CLOSED_INSUFFICIENT_HISTORY",
                "target_index": target_index,
            }
        )
        continue
    numbers = [int(number) for number in result["numbers"]]
    probabilities = [
        float(probability) for probability in result["probabilities"]
    ]
    if (
        result.get("method") != "XGBoost 梯度提升決策樹"
        or result.get("modelInfo", {}).get("trainingSize")
        != min(target_index, 1000)
        or result.get("modelInfo", {}).get("version") != "1.0"
        or result.get("modelInfo", {}).get("algorithm")
        != "XGBoost Multi-label"
    ):
        raise RuntimeError("frozen XGBoost result metadata changed")
    rows.append(
        {
            "confidence": float(result["confidence"]),
            "probabilities": probabilities,
            "status": "OK",
            "target_index": target_index,
            "ticket": numbers,
        }
    )

json.dump(
    {
        "numpy_version": numpy.__version__,
        "pandas_version": pandas.__version__,
        "python_version": ".".join(
            str(item) for item in sys.version_info[:3]
        ),
        "rows": rows,
        "sklearn_version": sklearn.__version__,
        "xgboost_version": xgboost.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityError(ValueError):
    """Frozen XGBoost artifacts or outputs violate the wave-64 contract."""


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


def _source_identity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
) -> dict[str, object]:
    frozen_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
    )
    source_path = frozen_source_directory.joinpath(METHOD_ID)
    if source_path.is_symlink() or not source_path.is_file():
        raise ParityError("extracted frozen XGBoost source is not a regular file")
    extracted_raw = source_path.read_bytes()
    blob_id = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
        )
        .decode("ascii")
        .strip()
    )
    if (
        frozen_raw != extracted_raw
        or len(frozen_raw) != SOURCE_BYTE_SIZE
        or hashlib.sha256(frozen_raw).hexdigest() != SOURCE_SHA256
        or blob_id != SOURCE_BLOB_ID
    ):
        raise ParityError("frozen XGBoost source identity changed")
    text = extracted_raw.decode("utf-8")
    for fragment in (
        "train_history = history[-1000:] if len(history) > 1000 else history",
        'if len(X) < 10:',
        'raise ValueError("訓練數據不足")',
        "clf = MultiOutputClassifier(xgb.XGBClassifier(",
        "n_estimators=50",
        "max_depth=3",
        "learning_rate=0.1",
        "objective='binary:logistic'",
        "eval_metric='logloss'",
        "n_jobs=-1",
        "for i in range(window_size, len(history)):",
        "all_possible_numbers = list(range(min_num, max_num + 1))",
        "sorted_numbers[:pick_count]",
    ):
        if fragment not in text:
            raise ParityError("frozen XGBoost behavior changed")
    return {
        "source_blob_id": blob_id,
        "source_byte_size": len(frozen_raw),
        "source_sha256": SOURCE_SHA256,
    }


def _load_history_input(path: Path) -> tuple[list[dict[str, object]], str]:
    if path.is_symlink() or not path.is_file():
        raise ParityError("history input must be a regular non-symlink file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HISTORY_INPUT_FILE_SHA256:
        raise ParityError("history input physical SHA-256 changed")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParityError("history input is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ParityError("history input must be an object")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("lottery_type") != "BIG_LOTTO"
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != HISTORY_INPUT_CANONICAL_SHA256
    ):
        raise ParityError("history input authority changed")
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list):
        raise ParityError("history input targets are missing")
    targets = cast(list[object], targets_raw)
    draws: list[dict[str, object]] = []
    for candidate in targets:
        if not isinstance(candidate, dict):
            raise ParityError("history input target is invalid")
        target = cast(dict[str, object], candidate)
        ticket = target.get("winning_main_numbers")
        if (
            type(target.get("draw_number")) is not str
            or type(target.get("draw_date")) is not str
            or not isinstance(ticket, list)
            or len(cast(list[object], ticket)) != 6
            or any(
                type(number) is not int
                for number in cast(list[object], ticket)
            )
        ):
            raise ParityError("history input target layout changed")
        numbers = cast(list[int], ticket)
        if (
            numbers != sorted(numbers)
            or len(set(numbers)) != 6
            or any(not 1 <= number <= 49 for number in numbers)
        ):
            raise ParityError("history input target ticket is invalid")
        draws.append(
            {
                "date": target["draw_date"],
                "draw": target["draw_number"],
                "numbers": numbers,
            }
        )
    if (
        len(draws) != 2149
        or draws[0]["draw"] != "96000001"
        or draws[-1]["draw"] != "115000073"
    ):
        raise ParityError("wave-64 target set changed")
    return draws, hashlib.sha256(raw).hexdigest()


def _reference_output(
    *,
    reference_python: Path,
    source_path: Path,
    draws: list[dict[str, object]],
    indices: list[int],
    omp_threads: int,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "OMP_NUM_THREADS": str(omp_threads),
            "PYTHONDONTWRITEBYTECODE": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        }
    )
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "closed_reason": CLOSED_REASON,
                "draws": draws,
                "indices": indices,
                "source_path": str(source_path),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen XGBoost reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError(
            "frozen XGBoost reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen XGBoost reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("pandas_version") != "2.1.3"
        or document.get("sklearn_version") != "1.3.2"
        or document.get("xgboost_version") != "2.0.2"
    ):
        raise ParityError("frozen XGBoost reference runtime changed")
    return document


def _full_reference_outputs(
    *,
    reference_python: Path,
    source_path: Path,
    draws: list[dict[str, object]],
    workers: int,
) -> list[dict[str, object]]:
    if workers < 1 or workers > 16:
        raise ParityError("workers must be between 1 and 16")
    shards = [
        list(range(worker, len(draws), workers))
        for worker in range(workers)
    ]
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:
        futures = [
            executor.submit(
                _reference_output,
                reference_python=reference_python,
                source_path=source_path,
                draws=draws,
                indices=indices,
                omp_threads=1,
            )
            for indices in shards
        ]
        documents = [future.result() for future in futures]
    by_index: dict[int, dict[str, object]] = {}
    for document in documents:
        rows_raw = document.get("rows")
        if not isinstance(rows_raw, list):
            raise ParityError("frozen XGBoost shard output changed")
        for candidate in cast(list[object], rows_raw):
            if not isinstance(candidate, dict):
                raise ParityError("frozen XGBoost result row changed")
            row = cast(dict[str, object], candidate)
            target_index = row.get("target_index")
            if type(target_index) is not int or target_index in by_index:
                raise ParityError("frozen XGBoost target coverage changed")
            by_index[target_index] = row
    if set(by_index) != set(range(len(draws))):
        raise ParityError("frozen XGBoost target coverage changed")
    return [by_index[index] for index in range(len(draws))]


def _validate_ticket(value: object) -> list[int]:
    if not isinstance(value, list):
        raise ParityError("frozen XGBoost ticket is missing")
    items = cast(list[object], value)
    if len(items) != 6 or any(type(number) is not int for number in items):
        raise ParityError("frozen XGBoost ticket must contain six integers")
    ticket = cast(list[int], items)
    if (
        ticket != sorted(ticket)
        or len(set(ticket)) != 6
        or any(not 1 <= number <= 49 for number in ticket)
    ):
        raise ParityError("frozen XGBoost ticket is not canonical")
    return ticket


def _probe_rows(document: dict[str, Any]) -> list[dict[str, object]]:
    rows_raw = document.get("rows")
    if not isinstance(rows_raw, list):
        raise ParityError("thread-parity probe rows changed")
    return [
        cast(dict[str, object], row)
        for row in cast(list[object], rows_raw)
        if isinstance(row, dict)
    ]


def verify_wave64_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    history_input: Path,
    reference_python: Path,
    workers: int,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the full wave-64 ticket ledger and parity proof."""

    source_artifact = _source_identity(
        frozen_root=frozen_root,
        frozen_source_directory=frozen_source_directory,
    )
    draws, history_input_file_sha256 = _load_history_input(history_input)
    source_path = frozen_source_directory.joinpath(METHOD_ID)
    rows = _full_reference_outputs(
        reference_python=reference_python,
        source_path=source_path,
        draws=draws,
        workers=workers,
    )
    probe_indices: list[int] = list(THREAD_PARITY_INDICES)
    probe_one = _reference_output(
        reference_python=reference_python,
        source_path=source_path,
        draws=draws,
        indices=probe_indices,
        omp_threads=1,
    )
    probe_repeat = _reference_output(
        reference_python=reference_python,
        source_path=source_path,
        draws=draws,
        indices=probe_indices,
        omp_threads=1,
    )
    probe_many = _reference_output(
        reference_python=reference_python,
        source_path=source_path,
        draws=draws,
        indices=probe_indices,
        omp_threads=8,
    )
    if not (
        _probe_rows(probe_one)
        == _probe_rows(probe_repeat)
        == _probe_rows(probe_many)
        == [rows[index] for index in probe_indices]
    ):
        raise ParityError(
            "XGBoost repeat or OpenMP thread-count parity failed"
        )

    targets: list[str] = []
    contexts: list[str] = []
    history_counts: list[int] = []
    tickets: list[list[list[int]] | None] = []
    probabilities: list[list[float] | None] = []
    confidences: list[float | None] = []
    closed: list[str | None] = []
    status_counts = {"CLOSED_INSUFFICIENT_HISTORY": 0, "OK": 0}
    for target_index, (draw, row) in enumerate(zip(draws, rows, strict=True)):
        targets.append(cast(str, draw["draw"]))
        contexts.append(
            hashlib.sha256(
                _canonical_bytes(
                    [
                        candidate["numbers"]
                        for candidate in draws[:target_index]
                    ]
                )
            ).hexdigest()
        )
        history_counts.append(min(target_index, 1000))
        status = row.get("status")
        if target_index < 15:
            if (
                status != "CLOSED_INSUFFICIENT_HISTORY"
                or row.get("closed_reason") != CLOSED_REASON
            ):
                raise ParityError("XGBoost insufficient-history boundary changed")
            tickets.append(None)
            probabilities.append(None)
            confidences.append(None)
            closed.append(CLOSED_REASON)
            status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
            continue
        if status != "OK":
            raise ParityError("executable XGBoost output changed")
        ticket = _validate_ticket(row.get("ticket"))
        probabilities_raw = row.get("probabilities")
        if (
            not isinstance(probabilities_raw, list)
            or len(cast(list[object], probabilities_raw)) != 6
            or any(
                type(value) is not float
                for value in cast(list[object], probabilities_raw)
            )
            or type(row.get("confidence")) is not float
        ):
            raise ParityError("XGBoost probability output changed")
        selected_probabilities = cast(list[float], probabilities_raw)
        tickets.append([ticket])
        probabilities.append(selected_probabilities)
        confidences.append(cast(float, row["confidence"]))
        closed.append(None)
        status_counts["OK"] += 1
    if status_counts != {
        "CLOSED_INSUFFICIENT_HISTORY": 15,
        "OK": 2134,
    }:
        raise ParityError("XGBoost execution coverage changed")

    ledger: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_reason": closed,
        "confidence_by_target": confidences,
        "context_numbers_sha256_by_target": contexts,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "history_input_draw_count": history_counts,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "legacy_method_id": METHOD_ID,
        "selected_probabilities_by_target": probabilities,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256": SOURCE_SHA256,
        "target_draw_numbers": targets,
        "tickets": tickets,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "causal_adapter_facts": {
            "history_input_order": "OLDEST_FIRST",
            "history_input_upper_bound": 1000,
            "minimum_history_draw_count": 15,
            "model_estimators_per_number": 50,
            "model_label_count": 49,
            "model_max_depth": 3,
            "native_configuration_count": 1,
            "native_ticket_count": 1,
            "source_n_jobs": -1,
            "target_stable_model_retraining": True,
        },
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "history_input_canonical_sha256": HISTORY_INPUT_CANONICAL_SHA256,
        "history_input_file_sha256": history_input_file_sha256,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": 2134,
        "native_ticket_count_distribution": {"1": 2134},
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "probability_sequence_sha256": hashlib.sha256(
            _canonical_bytes(probabilities)
        ).hexdigest(),
        "repeatability_probe_indices": probe_indices,
        "source_artifact": source_artifact,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "status_counts": status_counts,
        "thread_count_parity": {
            "omp_thread_counts": [1, 8],
            "status": "PASS",
            "target_indices": probe_indices,
        },
        "ticket_sequence_sha256": hashlib.sha256(
            _canonical_bytes(tickets)
        ).hexdigest(),
        "worker_count": workers,
    }
    parity["parity_sha256"] = hashlib.sha256(
        _canonical_bytes(parity)
    ).hexdigest()
    return ledger, parity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument(
        "--frozen-source-directory",
        required=True,
        type=Path,
    )
    parser.add_argument("--history-input", required=True, type=Path)
    parser.add_argument("--reference-python", required=True, type=Path)
    parser.add_argument("--workers", default=8, type=int)
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    ledger, parity = verify_wave64_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        history_input=args.history_input,
        reference_python=args.reference_python,
        workers=args.workers,
    )
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity_raw = _canonical_bytes(parity) + b"\n"
    args.ledger_output_file.write_bytes(ledger_raw)
    args.output_file.write_bytes(parity_raw)
    print(
        json.dumps(
            {
                "ledger_content_sha256": ledger["ledger_content_sha256"],
                "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
                "native_ticket_case_count": parity["native_ticket_case_count"],
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
                "ticket_sequence_sha256": parity["ticket_sequence_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
