#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Regenerate and verify every wave-57 HPSB-V2 native ticket."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_hpsb_native_portfolios_wave57 import (
    AUDITED_SOURCE_NATIVE_WAVE57_METHODS,
    CAUSAL_ELIGIBILITY_RULE,
    CONTEXT_POLICY,
    ENSEMBLE_ALIAS_METHOD_ID,
    FROZEN_SOURCE_COMMIT,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE57_METHOD,
    HPSB_METHOD_ID,
    LEDGER_SCHEMA_VERSION,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE57_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE57_METHODS,
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
    "BIG_LOTTO_LEGACY_HPSB_NATIVE_WAVE57_PARITY_V1"
)
_REFERENCE_SCRIPT = r"""
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root]

import numpy
import scipy
from lottery_api.models.ensemble_predictor import EnsemblePredictor
from lottery_api.models.hpsb_optimizer import HPSBOptimizer

draws = request["draws"]
rules = {
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,
    "name": "BIG_LOTTO",
}
hpsb_id = "lottery_api/models/hpsb_optimizer.py"
ensemble_id = "lottery_api/models/ensemble_predictor.py"
outputs = {hpsb_id: [], ensemble_id: []}
for target_index in range(len(draws)):
    history = draws[:target_index]
    result = HPSBOptimizer().predict_hpsb_v2(history, rules)
    outputs[hpsb_id].append([result["numbers"]])
    alias_result = EnsemblePredictor().predict_ensemble(history, rules)
    outputs[ensemble_id].append([alias_result["numbers"]])
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
    """Frozen artifacts or reference execution violate wave-57 parity."""


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
    hpsb_text = frozen_source_directory.joinpath(
        HPSB_METHOD_ID
    ).read_text(encoding="utf-8")
    ensemble_text = frozen_source_directory.joinpath(
        ENSEMBLE_ALIAS_METHOD_ID
    ).read_text(encoding="utf-8")
    engine_text = frozen_source_directory.joinpath(
        "lottery_api/models/unified_predictor.py"
    ).read_text(encoding="utf-8")
    adapter_text = frozen_source_directory.joinpath(
        "ai_lab/adapter.py"
    ).read_text(encoding="utf-8")
    hpsb_fragments = (
        "return self.predict_hpsb_dms(history, rules)",
        "audit_window: int = 15",
        "if len(history) < audit_window + 5:",
        "'statistical': self.engine.statistical_predict",
    )
    ensemble_fragments = (
        "dms_res = self.hpsb.predict_hpsb_dms(history, rules)",
        "AIAdapter.get_ai_prediction('transformer_v3_raw', history, rules)",
        "ai_weight = 0.0 # Ignore AI if it fails",
        "final_numbers = self.hpsb._apply_zdp",
        "def patch_ai_adapter():",
        'if __name__ == "__main__":',
        "pass",
    )
    if any(fragment not in hpsb_text for fragment in hpsb_fragments):
        raise ParityError("frozen HPSB public-entrypoint behavior changed")
    if any(fragment not in ensemble_text for fragment in ensemble_fragments):
        raise ParityError("frozen ensemble fallback behavior changed")
    if (
        "random.seed(len(history))" not in engine_text
        or "if method_name == 'transformer_v3':" not in adapter_text
        or "transformer_v3_raw" in adapter_text
    ):
        raise ParityError("frozen HPSB dependency behavior changed")
    return {
        HPSB_METHOD_ID: {
            "audit_window": 15,
            "entrypoint": "HPSBOptimizer.predict_hpsb_v2",
            "history_below_20_falls_back_to_weighted_hpsb": True,
            "native_local_configuration_count": 1,
            "native_ticket_count": 1,
            "statistical_rng_seed": "HISTORY_LENGTH",
        },
        ENSEMBLE_ALIAS_METHOD_ID: {
            "adapter_supports_transformer_v3_raw": False,
            "entrypoint": "EnsemblePredictor.predict_ensemble",
            "local_patch_invoked_by_entrypoint_or_main": False,
            "native_local_configuration_count": 1,
            "native_ticket_count": 1,
            "unsupported_ai_path_forces_ai_weight_zero": True,
        },
    }


def _reference_outputs(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(reference_python), "-c", _REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode("utf-8", errors="replace").strip()
            or "frozen HPSB reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError(
            "frozen HPSB reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityError("frozen HPSB reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
    ):
        raise ParityError("frozen HPSB reference runtime changed")
    return document


def verify_wave57_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
    prior_ledger: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the 2,149-ticket ledger and frozen-source parity proof."""

    source_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=method_id,
            expected_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[method_id]
            ),
        )
        for method_id in AUDITED_SOURCE_NATIVE_WAVE57_METHODS
    ]
    unique_support: dict[str, str] = {}
    for method_id in AUDITED_SOURCE_NATIVE_WAVE57_METHODS:
        for path, digest in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE57_METHOD[
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
    behavior_facts = _source_behavior_facts(frozen_source_directory)
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    if (
        len(pinned.draws) != 2149
        or pinned.draws[0].draw_number != "96000001"
        or pinned.draws[-1].draw_number != "115000073"
    ):
        raise ParityError("wave-57 full causal target set changed")
    draws: list[dict[str, object]] = [
        {
            "date": draw.draw_date.isoformat(),
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in pinned.draws
    ]
    reference = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    outputs_raw = reference.get("outputs")
    if not isinstance(outputs_raw, dict):
        raise ParityError("frozen HPSB ticket outputs changed")
    outputs = cast(dict[str, object], outputs_raw)
    if set(outputs) != set(AUDITED_SOURCE_NATIVE_WAVE57_METHODS):
        raise ParityError("frozen HPSB audited method outputs changed")
    typed_outputs: dict[str, list[list[list[int]]]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    for method_id in AUDITED_SOURCE_NATIVE_WAVE57_METHODS:
        method_raw = outputs[method_id]
        if not isinstance(method_raw, list):
            raise ParityError("frozen HPSB ticket sequence changed")
        typed_rows: list[list[list[int]]] = []
        for target_index, candidate in enumerate(
            cast(list[object], method_raw)
        ):
            if not isinstance(candidate, list):
                raise ParityError("frozen HPSB portfolio changed")
            portfolio = [
                _validate_ticket(
                    ticket,
                    context=(
                        f"{method_id} target {target_index} "
                        f"ticket {ticket_index}"
                    ),
                )
                for ticket_index, ticket in enumerate(
                    cast(list[object], candidate)
                )
            ]
            if len(portfolio) != 1:
                raise ParityError(
                    f"frozen HPSB native count changed: {method_id}"
                )
            typed_rows.append(portfolio)
        if len(typed_rows) != 2149:
            raise ParityError("frozen HPSB target count changed")
        typed_outputs[method_id] = typed_rows
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            _canonical_bytes(typed_rows)
        ).hexdigest()
    exact_alias_match_count = sum(
        hpsb == ensemble
        for hpsb, ensemble in zip(
            typed_outputs[HPSB_METHOD_ID],
            typed_outputs[ENSEMBLE_ALIAS_METHOD_ID],
            strict=True,
        )
    )
    if exact_alias_match_count != 2149:
        raise ParityError(
            "default ensemble is not an exact all-target HPSB-V2 alias"
        )
    target_draw_numbers = [draw.draw_number for draw in pinned.draws]
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
        for index in range(len(pinned.draws))
    ]
    ledger_outputs = {
        method_id: typed_outputs[method_id]
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE57_METHODS
    }
    ledger_source_hashes = {
        method_id: SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE57_METHOD[method_id]
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE57_METHODS
    }
    ledger_native_counts = {
        method_id: NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE57_METHOD[
            method_id
        ]
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE57_METHODS
    }
    regenerated: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "context_policy": CONTEXT_POLICY,
        "context_numbers_sha256_by_target": context_sha256,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "native_ticket_count_by_method": ledger_native_counts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": ledger_source_hashes,
        "target_draw_numbers": target_draw_numbers,
        "tickets_by_method": ledger_outputs,
    }
    regenerated["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(regenerated)
    ).hexdigest()
    ledger_raw = _canonical_bytes(regenerated) + b"\n"
    prior_targets, prior_contexts, prior_outputs = _load_prior_ledger(
        prior_ledger
    )
    if (
        target_draw_numbers[1:] != prior_targets
        or context_sha256[1:] != prior_contexts
    ):
        raise ParityError(
            "wave-57 regeneration database leaves prior-ledger history"
        )
    alias_outputs: dict[str, list[list[list[int]] | None]] = {
        method_id: [row for row in rows]
        for method_id, rows in typed_outputs.items()
    }
    cross_wave_outputs: dict[str, list[list[list[int]] | None]] = {
        method_id: [row for row in rows[1:]]
        for method_id, rows in typed_outputs.items()
    }
    document: dict[str, object] = {
        "alias_disposition": {
            "alias_method_id": ENSEMBLE_ALIAS_METHOD_ID,
            "canonical_method_id": HPSB_METHOD_ID,
            "exact_match_count": exact_alias_match_count,
            "reason_code": (
                "EXACT_ALL_TARGET_DEFAULT_ENTRYPOINT_ALIAS_TO_HPSB_V2"
            ),
            "target_count": 2149,
        },
        "audited_native_ticket_case_count": 4298,
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "cross_wave_exact_alias_candidates": _alias_candidates(
            cross_wave_outputs,
            prior_outputs,
            cross_ledger=True,
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "eligible_target_count": 2149,
        "exact_alias_candidates": _alias_candidates(
            alias_outputs,
            alias_outputs,
            cross_ledger=False,
        ),
        "first_target_history_draw_count": 0,
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": regenerated["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_ticket_case_count": 2149,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "support_artifacts": support_artifacts,
        "ticket_sequence_sha256_by_method": sequence_sha256_by_method,
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
    ledger, document = verify_wave57_parity(
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
    alias_disposition = cast(
        dict[str, object],
        document["alias_disposition"],
    )
    print(
        json.dumps(
            {
                "alias_match_count": alias_disposition[
                    "exact_match_count"
                ],
                "eligible_target_count": document[
                    "eligible_target_count"
                ],
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_raw
                ).hexdigest(),
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
