#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate and verify all wave-55 frozen checkpoint tickets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_checkpoint_native_portfolios_wave55 import (
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_BY_SOURCE_NATIVE_WAVE55_METHOD,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_TIME,
    CONTEXT_POLICY,
    FROZEN_SOURCE_COMMIT,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE55_METHOD,
    LEDGER_SCHEMA_VERSION,
    MODEL_CONTEXT_DRAW_COUNT,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD,
    ORTHOGONAL_METHOD_ID,
    PINNED_DATASET_SHA256,
    SIX_EXPERT_METHOD_ID,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)
from verify_biglotto_legacy_source_grid_wave48_parity import (
    _alias_candidates,
    _load_prior_ledger,
    _validate_ticket,
)

PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE55_PARITY_V1"
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
import scipy
import torch
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.orthogonal_portfolio import OrthogonalPortfolio
from ai_lab.scripts.six_expert_ensemble import SixExpertEnsemble
from models.unified_predictor import UnifiedPredictionEngine

draws = request["draws"]
target_indices = request["target_indices"]
rules = {
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,
    "name": "BIG_LOTTO",
}
orthogonal_id = "tools/predict_next_draw.py"
six_expert_id = "tools/predict_6expert.py"
outputs = {orthogonal_id: [], six_expert_id: []}
for target_index in target_indices:
    engine = UnifiedPredictionEngine()
    adapter = AIAdapter()
    result = OrthogonalPortfolio(
        engine,
        adapter,
    ).predict_orthogonal_3bet(draws[:target_index], rules)
    outputs[orthogonal_id].append(result["bets"])
for target_index in target_indices:
    engine = UnifiedPredictionEngine()
    adapter = AIAdapter()
    result = SixExpertEnsemble(
        engine,
        adapter,
    ).predict(draws[:target_index], rules)
    outputs[six_expert_id].append(result["bets"])
json.dump(
    {
        "mkldnn_enabled": torch.backends.mkldnn.enabled,
        "numpy_version": numpy.__version__,
        "outputs": outputs,
        "python_version": ".".join(str(item) for item in sys.version_info[:3]),
        "scipy_version": scipy.__version__,
        "torch_num_threads": torch.get_num_threads(),
        "torch_version": torch.__version__,
    },
    sys.stdout,
    separators=(",", ":"),
    sort_keys=True,
)
"""


class ParityError(ValueError):
    """Frozen artifacts or reference execution violate wave-55 parity."""


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
        ORTHOGONAL_METHOD_ID: (
            "predictor = OrthogonalPortfolio(engine, ai_adapter)",
            "res = predictor.predict_orthogonal_3bet(all_draws, rules)",
            "bets = res['bets']",
        ),
        SIX_EXPERT_METHOD_ID: (
            "predictor = SixExpertEnsemble(engine, ai_adapter)",
            "res = predictor.predict(all_draws, rules)",
            "bets = res['bets']",
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
            "full_history_is_reversed_to_oldest_first": True,
            "model_context_draw_count": 15,
            "native_local_configuration_count": 1,
            "native_ticket_count": (
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ),
            "portfolio_entrypoint_is_source_defined": True,
        }
    dependency_fragments = {
        "ai_lab/adapter.py": (
            "model.load_state_dict(torch.load(model_path, map_location='cpu'))",
            "model.eval()",
            "top_candidates': sorted_nums.tolist()[:30]",
        ),
        "ai_lab/scripts/orthogonal_portfolio.py": (
            "'bets': [bet1, bet2, bet3]",
            "ai_ranks = ai_res.get('top_candidates', [])[6:12]",
        ),
        "ai_lab/scripts/six_expert_ensemble.py": (
            "'bets': bets",
            "'experts': ['AI-Structural', 'HPSB-DMS', 'Graph', 'Hybrid', 'Gap', 'Tail']",
        ),
        "ai_lab/scripts/tail_number_predictor.py": (
            "random.seed(len(history))",
            "bet.extend(random.sample(hot_candidates, 4))",
        ),
    }
    for path, required in dependency_fragments.items():
        text = frozen_source_directory.joinpath(path).read_text(
            encoding="utf-8"
        )
        if any(fragment not in text for fragment in required):
            raise ParityError(
                f"frozen dependency behavior changed: {path}"
            )
    output["dependency_behavior"] = {
        "checkpoint_model_eval": True,
        "orthogonal_position_order": (
            "STRUCTURAL_AI_HPSB_DMS_HYBRID_BALANCE"
        ),
        "six_expert_position_order": (
            "STRUCTURAL_AI_HPSB_DMS_GRAPH_HYBRID_GAP_TAIL"
        ),
        "tail_rng_seed": "HISTORY_LENGTH",
    }
    return output


def _checkpoint_introduction_facts(
    frozen_root: Path,
) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    seen: set[str] = set()
    for checkpoint_path, checkpoint_sha256, checkpoint_blob_id in (
        CHECKPOINT_BY_SOURCE_NATIVE_WAVE55_METHOD.values()
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
        or document.get("scipy_version") != "1.12.0"
        or document.get("torch_num_threads") != 4
        or document.get("mkldnn_enabled") is not True
    ):
        raise ParityError("frozen checkpoint reference runtime changed")
    return document


def verify_wave55_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the 432-ticket ledger and its frozen-source parity proof."""

    source_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=method_id,
            expected_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD[method_id]
            ),
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS
    ]
    unique_support: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
        for path, digest in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE55_METHOD[
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
            CHECKPOINT_BY_SOURCE_NATIVE_WAVE55_METHOD.values()
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
        raise ParityError("wave-55 causal target set changed")
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
    if set(outputs) != set(SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS):
        raise ParityError("frozen checkpoint method outputs changed")
    typed_outputs: dict[str, list[list[list[int]]]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
        method_raw = outputs[method_id]
        if not isinstance(method_raw, list):
            raise ParityError("frozen checkpoint ticket sequence changed")
        rows = cast(list[object], method_raw)
        typed_rows: list[list[list[int]]] = []
        for target_offset, candidate in enumerate(rows):
            if not isinstance(candidate, list):
                raise ParityError("frozen checkpoint portfolio changed")
            portfolio = [
                _validate_ticket(
                    ticket,
                    context=(
                        f"{method_id} target {target_offset} "
                        f"ticket {ticket_index}"
                    ),
                )
                for ticket_index, ticket in enumerate(
                    cast(list[object], candidate)
                )
            ]
            if (
                len(portfolio)
                != NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                    method_id
                ]
            ):
                raise ParityError(
                    f"frozen checkpoint native count changed: {method_id}"
                )
            typed_rows.append(portfolio)
        if len(typed_rows) != 48:
            raise ParityError("frozen checkpoint target count changed")
        typed_outputs[method_id] = typed_rows
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            _canonical_bytes(typed_rows)
        ).hexdigest()
    subset_matches = sum(
        1
        for orthogonal, six_expert in zip(
            typed_outputs[ORTHOGONAL_METHOD_ID],
            typed_outputs[SIX_EXPERT_METHOD_ID],
            strict=True,
        )
        if orthogonal == [
            six_expert[0],
            six_expert[1],
            six_expert[3],
        ]
    )
    if subset_matches != 48:
        raise ParityError(
            "orthogonal-to-six-expert positional relation changed"
        )
    context_sha256 = [
        hashlib.sha256(
            json.dumps(
                [
                    list(draw.numbers)
                    for draw in pinned.draws[:index]
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
        "context_policy": CONTEXT_POLICY,
        "context_numbers_sha256_by_target": context_sha256,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "model_context_draw_count": MODEL_CONTEXT_DRAW_COUNT,
        "native_ticket_count_by_method": dict(
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD
        ),
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE55_METHOD
        ),
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": typed_outputs,
    }
    regenerated["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(regenerated)
    ).hexdigest()
    ledger_raw = _canonical_bytes(regenerated) + b"\n"
    prior_targets, prior_contexts, prior_outputs = _load_prior_ledger(
        prior_ledger
    )
    all_targets = [draw.draw_number for draw in pinned.draws[1:]]
    all_contexts = [
        hashlib.sha256(
            json.dumps(
                [list(draw.numbers) for draw in pinned.draws[:index]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for index in range(1, len(pinned.draws))
    ]
    if all_targets != prior_targets or all_contexts != prior_contexts:
        raise ParityError(
            "wave-55 regeneration database leaves pinned prior-ledger history"
        )
    full_outputs: dict[str, list[list[list[int]] | None]] = {
        method_id: [None for _ in all_targets]
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS
    }
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE55_METHODS:
        for target_index, portfolio in zip(
            target_indices,
            typed_outputs[method_id],
            strict=True,
        ):
            full_outputs[method_id][target_index - 1] = portfolio
    document: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "checkpoint_artifacts": checkpoint_artifacts,
        "checkpoint_introduction_facts": introduction_facts,
        "cross_method_positional_subset_match_count": subset_matches,
        "cross_wave_exact_alias_candidates": _alias_candidates(
            full_outputs,
            prior_outputs,
            cross_ledger=True,
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "eligible_target_count": len(target_indices),
        "exact_alias_candidates": _alias_candidates(
            full_outputs,
            full_outputs,
            cross_ledger=False,
        ),
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": regenerated["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": sum(
            len(rows)
            * NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE55_METHOD[
                method_id
            ]
            for method_id, rows in typed_outputs.items()
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
    return regenerated, document


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
    parser.add_argument("--prior-ledger", required=True, type=Path)
    parser.add_argument("--ledger-output-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.ledger_output_file, args.output_file):
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing output: {path}")
    ledger, document = verify_wave55_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
        prior_ledger=args.prior_ledger,
    )
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_raw)
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
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_raw
                ).hexdigest(),
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
