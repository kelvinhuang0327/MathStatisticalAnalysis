#!/usr/bin/env python3
"""Regenerate and verify all wave-44 frozen checkpoint tickets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_checkpoint_native_portfolios_wave44 import (
    BENCHMARK_AI_METHOD_ID,
    BENCHMARK_AI_ZDP_METHOD_ID,
    BENCHMARK_V3_METHOD_ID,
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_TIME,
    FROZEN_SOURCE_COMMIT,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE44_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_RESOURCE_NAME,
    LEDGER_SCHEMA_VERSION,
    MODEL_CONTEXT_DRAW_COUNT,
    PINNED_DATASET_SHA256,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE44_PARITY_V1"
)
_REFERENCE_SCRIPT = r"""
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api"), os.path.join(root, "ai_lab")]

import numpy
import torch
from ai_lab.scripts.benchmark_ai import TransformerPredictor
from ai_lab.scripts.benchmark_ai_zdp import TransformerZDPPredictor
from ai_lab.scripts.benchmark_v3 import V3Predictor

draws = request["draws"]
target_indices = request["target_indices"]
rules = {"pickCount": 6, "maxNumber": 49}
specs = [
    (
        "ai_lab/scripts/benchmark_ai.py",
        TransformerPredictor,
        "ai_lab/ai_models/finetuned_best.pth",
    ),
    (
        "ai_lab/scripts/benchmark_ai_zdp.py",
        TransformerZDPPredictor,
        "ai_lab/ai_models/finetuned_best.pth",
    ),
    (
        "ai_lab/scripts/benchmark_v3.py",
        V3Predictor,
        "ai_lab/ai_models/v3_deep_resonance.pth",
    ),
]
outputs = {}
for method_id, predictor_type, checkpoint in specs:
    predictor = predictor_type(checkpoint)
    outputs[method_id] = [
        predictor.predict(draws[:target_index], rules)["numbers"]
        for target_index in target_indices
    ]
json.dump(
    {
        "mkldnn_enabled": torch.backends.mkldnn.enabled,
        "numpy_version": numpy.__version__,
        "outputs": outputs,
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "torch_num_threads": torch.get_num_threads(),
        "torch_version": torch.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityError(ValueError):
    """Frozen artifacts or reference execution violate wave-44 parity."""


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


def _artifact(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    path: str,
    expected_sha256: str,
) -> dict[str, object]:
    git_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{path}",
    )
    extracted_path = frozen_source_directory.joinpath(path)
    if not extracted_path.is_file():
        raise ParityError(f"extracted frozen artifact is missing: {path}")
    extracted_raw = extracted_path.read_bytes()
    if (
        hashlib.sha256(git_raw).hexdigest() != expected_sha256
        or hashlib.sha256(extracted_raw).hexdigest() != expected_sha256
        or git_raw != extracted_raw
    ):
        raise ParityError(f"frozen artifact identity changed: {path}")
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
        "sha256": expected_sha256,
        "source_blob_id": blob_id,
    }


def _source_behavior_facts(
    frozen_source_directory: Path,
) -> dict[str, object]:
    fragments = {
        BENCHMARK_AI_METHOD_ID: (
            "class TransformerPredictor:",
            "context_draws = [d['numbers'] for d in history[-seq_len:]]",
            "probs[0] = -1",
            "predicted_numbers.append(int(idx))",
            '("DMS (SOTA Baseline)", hpsb_v2.predict_hpsb_v2)',
            '("Transformer (AI-Lab)", ai_predictor.predict)',
        ),
        BENCHMARK_AI_ZDP_METHOD_ID: (
            "class TransformerZDPPredictor:",
            "MAX_PER_ZONE = 3",
            "final_numbers = self._apply_zdp(candidates, pick_count, rules)",
            '("Transformer (Raw)", None)',
            '("Transformer + ZDP", ai_predictor.predict)',
        ),
        BENCHMARK_V3_METHOD_ID: (
            "class V3Predictor:",
            "stats.append(self.dataset._extract_v3_stats(context_draws[i], prev))",
            "logits = self.model(x, s)",
            "final_numbers = self._apply_zdp(candidates, pick_count, rules)",
            '("U-HPE V3 (Deep Resonance)", v3_predictor.predict)',
        ),
    }
    output: dict[str, object] = {}
    for method_id, required in fragments.items():
        text = frozen_source_directory.joinpath(method_id).read_text(
            encoding="utf-8"
        )
        if any(fragment not in text for fragment in required):
            raise ParityError(
                f"frozen source behavior changed: {method_id}"
            )
        output[method_id] = {
            "imported_comparators_are_benchmark_rows": True,
            "local_predictor_class_is_source_defined": True,
            "model_context_draw_count": 15,
            "native_local_configuration_count": 1,
            "ranked_legal_candidate_count": 49,
        }
    return output


def _checkpoint_introduction_facts(
    frozen_root: Path,
) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    seen: set[str] = set()
    for checkpoint_path, checkpoint_sha256, checkpoint_blob_id in (
        CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD.values()
    ):
        if checkpoint_path in seen:
            continue
        seen.add(checkpoint_path)
        log_rows = (
            _git(
                frozen_root,
                "log",
                "--diff-filter=A",
                "--follow",
                "--format=%H|%aI|%cI",
                "--",
                checkpoint_path,
            )
            .decode("utf-8")
            .splitlines()
        )
        if log_rows != [
            (
                f"{CHECKPOINT_INTRODUCTION_COMMIT}|"
                f"{CHECKPOINT_INTRODUCTION_TIME}|"
                f"{CHECKPOINT_INTRODUCTION_TIME}"
            )
        ]:
            raise ParityError(
                f"checkpoint introduction history changed: {checkpoint_path}"
            )
        introduction_blob = (
            _git(
                frozen_root,
                "rev-parse",
                f"{CHECKPOINT_INTRODUCTION_COMMIT}:{checkpoint_path}",
            )
            .decode("ascii")
            .strip()
        )
        frozen_blob = (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{checkpoint_path}",
            )
            .decode("ascii")
            .strip()
        )
        if introduction_blob != checkpoint_blob_id or frozen_blob != checkpoint_blob_id:
            raise ParityError(
                f"checkpoint blob history changed: {checkpoint_path}"
            )
        facts.append(
            {
                "artifact_introduction_commit": (
                    CHECKPOINT_INTRODUCTION_COMMIT
                ),
                "artifact_introduction_time": (
                    CHECKPOINT_INTRODUCTION_TIME
                ),
                "checkpoint_path": checkpoint_path,
                "checkpoint_sha256": checkpoint_sha256,
                "source_blob_id": checkpoint_blob_id,
            }
        )
    return facts


def _reference_outputs(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
    target_indices: list[int],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "source_root": str(frozen_source_directory),
                "target_indices": target_indices,
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen checkpoint reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError(
            "frozen checkpoint reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen checkpoint reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("torch_version") != "2.8.0"
        or document.get("numpy_version") != "1.26.2"
        or document.get("torch_num_threads") != 4
        or document.get("mkldnn_enabled") is not True
    ):
        raise ParityError("frozen checkpoint reference runtime changed")
    return document


def verify_wave44_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> dict[str, object]:
    """Regenerate all 144 native tickets and verify the packaged ledger."""

    if expected_database_sha256 != PINNED_DATASET_SHA256:
        raise ParityError("wave-44 parity requires the pinned full dataset")
    source_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=method_id,
            expected_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD[method_id]
            ),
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
    ]
    unique_support: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
        for path, digest in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE44_METHOD[
                method_id
            ]
        ):
            previous = unique_support.setdefault(path, digest)
            if previous != digest:
                raise ParityError("support artifact identity conflicts")
    support_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=digest,
        )
        for path, digest in sorted(unique_support.items())
    ]
    unique_checkpoints = {
        path: digest
        for path, digest, _blob_id in (
            CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD.values()
        )
    }
    checkpoint_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=digest,
        )
        for path, digest in sorted(unique_checkpoints.items())
    ]
    introduction_facts = _checkpoint_introduction_facts(frozen_root)
    behavior_facts = _source_behavior_facts(frozen_source_directory)

    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    draws: list[dict[str, object]] = [
        {
            "date": draw.draw_date.isoformat(),
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in pinned.draws
    ]
    target_indices = [
        index
        for index, draw in enumerate(pinned.draws)
        if draw.draw_date.isoformat() > "2026-02-24"
    ]
    target_draw_numbers = [
        pinned.draws[index].draw_number for index in target_indices
    ]
    if (
        len(target_indices) != 48
        or target_draw_numbers[0] != "115000026"
        or target_draw_numbers[-1] != "115000073"
    ):
        raise ParityError("wave-44 causal target set changed")
    reference = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
        target_indices=target_indices,
    )
    outputs_raw = reference.get("outputs")
    if not isinstance(outputs_raw, dict):
        raise ParityError("frozen checkpoint ticket outputs changed")
    outputs = cast(dict[str, object], outputs_raw)
    if set(outputs) != set(SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS):
        raise ParityError("frozen checkpoint method outputs changed")
    typed_outputs: dict[str, list[list[int]]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
        method_raw = outputs[method_id]
        if not isinstance(method_raw, list):
            raise ParityError("frozen checkpoint ticket sequence changed")
        rows = cast(list[object], method_raw)
        typed_rows: list[list[int]] = []
        for candidate in rows:
            if not isinstance(candidate, list):
                raise ParityError("frozen checkpoint ticket changed")
            values = cast(list[object], candidate)
            if (
                len(values) != 6
                or any(type(number) is not int for number in values)
            ):
                raise ParityError("frozen checkpoint ticket changed")
            typed_rows.append(cast(list[int], values))
        if len(typed_rows) != 48:
            raise ParityError("frozen checkpoint ticket count changed")
        typed_outputs[method_id] = typed_rows
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            json.dumps(typed_rows, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    context_sha256 = [
        hashlib.sha256(
            json.dumps(
                [
                    list(draw.numbers)
                    for draw in pinned.draws[
                        index - MODEL_CONTEXT_DRAW_COUNT : index
                    ]
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for index in target_indices
    ]
    regenerated: dict[str, object] = {
        "artifact_introduction_commit": CHECKPOINT_INTRODUCTION_COMMIT,
        "artifact_introduction_time": CHECKPOINT_INTRODUCTION_TIME,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "context_draw_count": MODEL_CONTEXT_DRAW_COUNT,
        "context_numbers_sha256_by_target": context_sha256,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": typed_outputs,
    }
    regenerated["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(regenerated)
    ).hexdigest()
    regenerated_raw = _canonical_bytes(regenerated) + b"\n"
    packaged_raw = (
        files("lottolab.strategies.data")
        .joinpath(LEDGER_RESOURCE_NAME)
        .read_bytes()
    )
    if (
        regenerated["ledger_content_sha256"] != LEDGER_CONTENT_SHA256
        or hashlib.sha256(regenerated_raw).hexdigest()
        != LEDGER_FILE_SHA256
        or regenerated_raw != packaged_raw
    ):
        raise ParityError(
            "regenerated tickets do not match the packaged wave-44 ledger"
        )
    document: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "checkpoint_artifacts": checkpoint_artifacts,
        "checkpoint_introduction_facts": introduction_facts,
        "dataset_sha256": pinned.database_sha256_before,
        "eligible_target_count": len(target_indices),
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": LEDGER_CONTENT_SHA256,
        "ledger_file_sha256": LEDGER_FILE_SHA256,
        "native_ticket_case_count": (
            len(target_indices)
            * len(SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS)
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "support_artifacts": support_artifacts,
        "ticket_sequence_sha256_by_method": (
            sequence_sha256_by_method
        ),
    }
    document["parity_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


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
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = verify_wave44_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(_canonical_bytes(document) + b"\n")
    print(
        json.dumps(
            {
                "eligible_target_count": document[
                    "eligible_target_count"
                ],
                "native_ticket_case_count": document[
                    "native_ticket_case_count"
                ],
                "output_file": str(args.output_file),
                "parity_sha256": document["parity_sha256"],
                "status": document["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
