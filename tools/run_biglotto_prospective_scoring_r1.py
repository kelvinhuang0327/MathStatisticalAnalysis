"""Minimal, offline prospective BIG_LOTTO scoring CLI and adapter (Python 3.9).

Directly reuses tools/score_biglotto_prospective_r1.py.
Only implements:
  Fixed JSON input -> Original verified scoring API -> Deterministic JSON output.

No prediction generation, network access, DB mutation, or replay adapters.
Diagnostic results only; no verification or lift claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure repository root is on sys.path so tools.score_biglotto_prospective_r1 is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import tools.score_biglotto_prospective_r1 as scorer_engine
except ImportError:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import score_biglotto_prospective_r1 as scorer_engine

ContractError = scorer_engine.ContractError
six_number_baseline = scorer_engine.six_number_baseline
score_biglotto_prospective = scorer_engine.score_biglotto_prospective

FORBIDDEN_VERIFIED_VALUES = frozenset({"VERIFIED", "PROVED", "TRUE", "PASS"})
FORBIDDEN_OUTPUT_FLAGS = frozenset({"-o", "--output", "--out", "--output-file", "--output-path"})

ERROR_CODE_MAP = {
    "MISSING_CUTOFF": "MISSING_INPUT_CUTOFF",
    "TARGET_INSIDE_INPUT": "CUTOFF_AFTER_TARGET",
    "CUTOFF_NOT_BEFORE_CAPTURE": "CUTOFF_AFTER_TARGET",
    "MULTIPLE_TICKETS_WITHOUT_CONTRACT": "INVALID_TICKET",
    "INVALID_NUMBERS": "INVALID_TICKET",
    "INVALID_NUMBER_COUNT": "INVALID_TICKET",
    "INVALID_NUMBER_TYPE": "INVALID_TICKET",
    "OUT_OF_RANGE_NUMBER": "INVALID_TICKET",
    "DUPLICATE_NUMBERS": "INVALID_TICKET",
}


def _load_json_file(path_or_str: Union[str, Path], label: str) -> Any:
    path = Path(path_or_str)
    if not path.is_file():
        raise ContractError("WRONG_INPUT_FORMAT", f"{label} file not found: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise ContractError("WRONG_INPUT_FORMAT", f"failed reading {label} file: {exc}") from exc
    try:
        return json.loads(content)
    except Exception as exc:
        raise ContractError("WRONG_INPUT_FORMAT", f"invalid JSON in {label} file: {exc}") from exc


def run_biglotto_prospective_scoring(
    predictions: Union[str, Path, Sequence[Mapping]],
    outcomes: Union[str, Path, Sequence[Mapping]],
    contract: Union[str, Path, Mapping],
    *,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute prospective BIG_LOTTO scoring using verified scoring engine."""
    # Gate B & Gate E: UNEXPECTED_OUTPUT_PATH
    if output_path is not None:
        raise ContractError(
            "UNEXPECTED_OUTPUT_PATH",
            "output paths are strictly prohibited; results must be emitted to stdout only",
        )

    # 1. Load predictions
    if isinstance(predictions, (str, Path)):
        predictions_data = _load_json_file(predictions, "predictions")
    else:
        predictions_data = predictions
    if not isinstance(predictions_data, (list, tuple)):
        raise ContractError("WRONG_INPUT_FORMAT", "predictions must be a JSON array")

    # 2. Load outcomes
    if isinstance(outcomes, (str, Path)):
        outcomes_data = _load_json_file(outcomes, "outcomes")
    else:
        outcomes_data = outcomes
    if not isinstance(outcomes_data, (list, tuple)):
        raise ContractError("WRONG_INPUT_FORMAT", "outcomes must be a JSON array")

    # 3. Load contract
    if isinstance(contract, (str, Path)):
        contract_data = _load_json_file(contract, "contract")
    else:
        contract_data = contract
    if not isinstance(contract_data, Mapping):
        raise ContractError("WRONG_INPUT_FORMAT", "contract must be a JSON object")

    # Gate E: UNEXPECTED_OUTPUT_PATH in contract
    for key in ("output_path", "OUTPUT_PATH", "output", "OUTPUT"):
        if key in contract_data and contract_data[key] is not None:
            raise ContractError(
                "UNEXPECTED_OUTPUT_PATH",
                "contract cannot specify an output path; results are stdout only",
            )

    # Gate E: FALSE_VERIFIED_STATUS & FALSE_SUCCESS_CLAIM in contract
    for key in ("EVIDENCE_STATUS", "ORIGINAL_PARITY", "ORIGINAL_HISTORICAL_PARITY"):
        val = contract_data.get(key)
        if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
            raise ContractError(
                "FALSE_VERIFIED_STATUS",
                f"unauthorized verified status claim: {key}={val}",
            )

    for key in (
        "PREDICTIVE_IMPROVEMENT",
        "PREDICTIVE_SUCCESS_EVIDENCE",
        "SIGNIFICANT_LIFT",
        "ROI_IMPROVED",
    ):
        val = contract_data.get(key)
        if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
            raise ContractError(
                "FALSE_SUCCESS_CLAIM",
                f"unauthorized prospective success claim: {key}={val}",
            )

    # Gate E: WRONG_BASELINE
    baseline_id = contract_data.get("BASELINE_IDENTITY")
    if baseline_id is not None and baseline_id not in (
        "HYPERGEOMETRIC_6_OF_49",
        "HYPERGEOMETRIC_6_OF_49_SINGLE_TICKET",
    ):
        raise ContractError("WRONG_BASELINE", f"invalid BASELINE_IDENTITY: {baseline_id}")

    mean_baseline = contract_data.get("MEAN_BASELINE")
    if mean_baseline is not None and mean_baseline not in ("36/49", 36 / 49):
        raise ContractError("WRONG_BASELINE", f"invalid MEAN_BASELINE: {mean_baseline}")

    if "BASELINE" in contract_data:
        raise ContractError("WRONG_BASELINE", "baseline cannot be overridden in evaluation contract")

    # Gate E: FALSE_VERIFIED_STATUS & FALSE_SUCCESS_CLAIM & SPECIAL_NUMBER_INCLUDED in predictions/outcomes
    for p in predictions_data:
        if isinstance(p, Mapping):
            for key in ("EVIDENCE_STATUS", "ORIGINAL_PARITY", "ORIGINAL_HISTORICAL_PARITY"):
                val = p.get(key)
                if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                    raise ContractError(
                        "FALSE_VERIFIED_STATUS",
                        f"prediction claims verified status: {key}={val}",
                    )
            for key in (
                "PREDICTIVE_IMPROVEMENT",
                "PREDICTIVE_SUCCESS_EVIDENCE",
                "SIGNIFICANT_LIFT",
                "ROI_IMPROVED",
            ):
                val = p.get(key)
                if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                    raise ContractError(
                        "FALSE_SUCCESS_CLAIM",
                        f"prediction claims success: {key}={val}",
                    )
            if any("SPECIAL" in str(k).upper() for k in p):
                raise ContractError("SPECIAL_NUMBER_INCLUDED", "special numbers not permitted in prediction")

    for o in outcomes_data:
        if isinstance(o, Mapping):
            for key in ("EVIDENCE_STATUS", "ORIGINAL_PARITY", "ORIGINAL_HISTORICAL_PARITY"):
                val = o.get(key)
                if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                    raise ContractError(
                        "FALSE_VERIFIED_STATUS",
                        f"outcome claims verified status: {key}={val}",
                    )
            for key in (
                "PREDICTIVE_IMPROVEMENT",
                "PREDICTIVE_SUCCESS_EVIDENCE",
                "SIGNIFICANT_LIFT",
                "ROI_IMPROVED",
            ):
                val = o.get(key)
                if (isinstance(val, str) and val.upper() in FORBIDDEN_VERIFIED_VALUES) or val is True:
                    raise ContractError(
                        "FALSE_SUCCESS_CLAIM",
                        f"outcome claims success: {key}={val}",
                    )
            if any("SPECIAL" in str(k).upper() for k in o):
                raise ContractError("SPECIAL_NUMBER_INCLUDED", "special numbers not permitted in outcome")

    # Extract contract parameters
    exp_id = contract_data.get("experiment_id")
    if exp_id is None:
        exp_id = contract_data.get("EXPERIMENT_ID")

    strat_id = contract_data.get("strategy_identity")
    if strat_id is None:
        strat_id = contract_data.get("STRATEGY_IDENTITY")

    draw_ids = contract_data.get("expected_draw_ids")
    if draw_ids is None:
        draw_ids = contract_data.get("EXPECTED_DRAW_IDS")

    if exp_id is None:
        raise ContractError("WRONG_INPUT_FORMAT", "contract missing experiment_id")
    if strat_id is None:
        raise ContractError("WRONG_INPUT_FORMAT", "contract missing strategy_identity")
    if draw_ids is None:
        raise ContractError("WRONG_INPUT_FORMAT", "contract missing expected_draw_ids")

    # Call original verified scoring tool
    try:
        raw_result = scorer_engine.score_biglotto_prospective(
            predictions_data,
            outcomes_data,
            experiment_id=exp_id,
            strategy_identity=strat_id,
            expected_draw_ids=draw_ids,
        )
    except ContractError as exc:
        mapped_code = ERROR_CODE_MAP.get(exc.code, exc.code)
        detail = exc.args[0].split(": ", 1)[-1] if ": " in exc.args[0] else str(exc)
        raise ContractError(mapped_code, detail) from exc

    # Format output maintaining all original values, adding EXPERIMENT_ID and BASELINE_IDENTITY as required by Gate C
    output = dict(raw_result)
    output["EXPERIMENT_ID"] = raw_result["FIXED_EXPERIMENT_ID"]
    output["BASELINE_IDENTITY"] = "HYPERGEOMETRIC_6_OF_49_SINGLE_TICKET"
    if isinstance(output.get("BASELINE"), dict):
        output["BASELINE"]["BASELINE_IDENTITY"] = "HYPERGEOMETRIC_6_OF_49_SINGLE_TICKET"
        output["BASELINE"]["MEAN_BASELINE"] = "36/49"
    return output


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for running prospective BIG_LOTTO scoring."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Offline prospective BIG_LOTTO scoring CLI entry point."
    )
    parser.add_argument("--predictions", "--predictions-file", dest="predictions", default=None)
    parser.add_argument("--outcomes", "--outcomes-file", dest="outcomes", default=None)
    parser.add_argument("--contract", "--contract-file", dest="contract", default=None)
    parser.add_argument("--input", "--input-file", "--combined", dest="combined", default=None)
    parser.add_argument(
        "-o",
        "--output",
        "--out",
        "--output-file",
        "--output-path",
        dest="output",
        default=None,
    )
    parser.add_argument("positional_args", nargs="*", default=[])

    # Check for forbidden output flags in raw argv before or during parsing
    for arg in argv:
        for prefix in ("-o", "--output", "--out", "--output-file", "--output-path"):
            if arg == prefix or arg.startswith(prefix + "="):
                sys.stderr.write(
                    "UNEXPECTED_OUTPUT_PATH: output paths are strictly prohibited; results must be emitted to stdout only\n"
                )
                return 1

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    if args.output is not None:
        sys.stderr.write(
            "UNEXPECTED_OUTPUT_PATH: output paths are strictly prohibited; results must be emitted to stdout only\n"
        )
        return 1

    predictions = args.predictions
    outcomes = args.outcomes
    contract = args.contract
    combined = args.combined

    pos = args.positional_args
    if combined is not None:
        data = _load_json_file(combined, "combined input")
        if not isinstance(data, Mapping):
            sys.stderr.write("WRONG_INPUT_FORMAT: combined input must be a JSON object\n")
            return 1
        predictions = data.get("predictions")
        outcomes = data.get("outcomes")
        contract = data.get("contract") if "contract" in data else data
    elif predictions is None and len(pos) == 1:
        single_path = Path(pos[0])
        if single_path.is_file():
            try:
                data = json.loads(single_path.read_text(encoding="utf-8"))
                if isinstance(data, Mapping) and "predictions" in data and "outcomes" in data:
                    predictions = data.get("predictions")
                    outcomes = data.get("outcomes")
                    contract = data.get("contract") if "contract" in data else data
                else:
                    predictions = pos[0]
            except Exception:
                predictions = pos[0]
        else:
            predictions = pos[0]
    else:
        if predictions is None and len(pos) >= 1:
            predictions = pos[0]
        if outcomes is None and len(pos) >= 2:
            outcomes = pos[1]
        if contract is None and len(pos) >= 3:
            contract = pos[2]

    if predictions is None or outcomes is None or contract is None:
        sys.stderr.write(
            "WRONG_INPUT_FORMAT: missing required input arguments (predictions, outcomes, contract)\n"
        )
        return 1

    try:
        result = run_biglotto_prospective_scoring(
            predictions,
            outcomes,
            contract,
            output_path=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ContractError as exc:
        sys.stderr.write(f"{exc.code}: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"UNHANDLED_ERROR: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
