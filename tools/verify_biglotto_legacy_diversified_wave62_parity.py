#!/usr/bin/env python3
"""Regenerate wave-62 diversified native portfolios from frozen source."""

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
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
ENSEMBLE_METHOD_ID = "tools/biglotto_diversified_ensemble.py"
BACKTEST_METHOD_ID = "tools/backtest_diversified_3bet.py"
METHOD_IDS = (ENSEMBLE_METHOD_ID, BACKTEST_METHOD_ID)
SOURCE_SHA256_BY_METHOD = {
    ENSEMBLE_METHOD_ID: (
        "36dbfc14b360d0961b429e7e7a424340c9e81d20886e4d9814b5306c82e9ee7f"
    ),
    BACKTEST_METHOD_ID: (
        "03acff1d1bf7f6375b011bd3c6d5750cf4c58569396fb80e85c4820f243c6c17"
    ),
}
SUPPORT_ARTIFACTS = {
    "lottery_api/common.py": (
        "c2da77b6e86e32d9cb41fbedb1be80cf62225ac1afff845d4b5bf28a8baf85d2"
    ),
    "lottery_api/database.py": (
        "9fa60bd417050f630af1cbef059550d4ae4cfb7644dac20e0489a16a88b3478a"
    ),
    "lottery_api/models/advanced_strategies.py": (
        "91c682887cd000fac721e85b77c6a3692aeb90a08981bbc39184ee33997666af"
    ),
    "lottery_api/models/biglotto_graph.py": (
        "4b5129659aa19628bb9d361b28ba35b65fd79f769f4bf00718c0cb7f45d62e90"
    ),
    "lottery_api/models/unified_predictor.py": (
        "32d0112c95ce33306002b2f4e13e2c768ff7612c0eb8750cd453cba73575e004"
    ),
}
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_DIVERSIFIED_WAVE62_TICKET_LEDGER_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DIVERSIFIED_WAVE62_PARITY_V1"
)
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_NETWORKX_3_2_1_"
    "ENSEMBLE_SEED42_PER_TARGET_AND_BACKTEST_SEED123_PER_HORIZON"
)
INSUFFICIENT_HISTORY_REASON = (
    "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
)
OUTSIDE_HORIZON_REASON = (
    "TARGET_OUTSIDE_FROZEN_SOURCE_MAIN_HORIZONS_150_AND_500"
)
_REFERENCE_SCRIPT = r"""
import contextlib
import io
import json
import os
import sys

request = json.load(sys.stdin)
root = request["source_root"]
os.chdir(root)
sys.path[:0] = [root, os.path.join(root, "lottery_api")]

import networkx
import numpy
import scipy
from tools.biglotto_diversified_ensemble import DiversifiedEnsemble

draws = request["draws"]
ensemble_id = "tools/biglotto_diversified_ensemble.py"
backtest_id = "tools/backtest_diversified_3bet.py"
outputs = {
    ensemble_id: [None for _ in draws],
    backtest_id: [None for _ in draws],
}
errors = {
    ensemble_id: [
        request["insufficient_history_reason"]
        if index < 50
        else None
        for index in range(len(draws))
    ],
    backtest_id: [
        request["outside_horizon_reason"]
        if index < len(draws) - 500
        else None
        for index in range(len(draws))
    ],
}
configuration_counts = {
    ensemble_id: [None for _ in draws],
    backtest_id: [None for _ in draws],
}

for index in range(50, len(draws)):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = DiversifiedEnsemble(seed=42).predict_3bets(
                history=list(reversed(draws[:index]))
            )
        outputs[ensemble_id][index] = [
            row["numbers"] for row in result
        ]
        configuration_counts[ensemble_id][index] = 1
    except Exception as exc:
        errors[ensemble_id][index] = (
            "FROZEN_SOURCE_EXECUTION_ERROR:"
            + type(exc).__name__
            + ":"
            + str(exc)
        )

for horizon in (150, 500):
    import random

    random.seed(123)
    numpy.random.seed(123)
    predictor = DiversifiedEnsemble(seed=123)
    for index in range(len(draws) - horizon, len(draws)):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = predictor.predict_3bets(
                    history=list(reversed(draws[:index]))
                )
            tickets = [row["numbers"] for row in result]
            if outputs[backtest_id][index] is None:
                outputs[backtest_id][index] = []
                configuration_counts[backtest_id][index] = 0
            outputs[backtest_id][index].extend(tickets)
            configuration_counts[backtest_id][index] += 1
        except Exception as exc:
            outputs[backtest_id][index] = None
            configuration_counts[backtest_id][index] = None
            errors[backtest_id][index] = (
                "FROZEN_SOURCE_EXECUTION_ERROR:"
                + "H"
                + str(horizon)
                + ":"
                + type(exc).__name__
                + ":"
                + str(exc)
            )

json.dump(
    {
        "configuration_counts": configuration_counts,
        "errors": errors,
        "networkx_version": networkx.__version__,
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
    """Frozen artifacts or source output violate wave-62 parity."""


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
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
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
    extracted_raw = frozen_source_directory.joinpath(path).read_bytes()
    if (
        hashlib.sha256(git_raw).hexdigest() != expected_sha256
        or hashlib.sha256(extracted_raw).hexdigest() != expected_sha256
        or git_raw != extracted_raw
    ):
        raise ParityError(f"frozen artifact identity changed: {path}")
    return {
        "path": path,
        "sha256": expected_sha256,
        "source_blob_id": (
            _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{path}",
            )
            .decode("ascii")
            .strip()
        ),
    }


def _validate_ticket(value: object, *, context: str) -> list[int]:
    if not isinstance(value, list):
        raise ParityError(f"{context}: ticket is not an array")
    values = cast(list[object], value)
    integers = (
        cast(list[int], values)
        if all(type(number) is int for number in values)
        else []
    )
    canonical = sorted(integers)
    if (
        len(canonical) != 6
        or len(set(canonical)) != 6
        or any(not 1 <= number <= 49 for number in canonical)
    ):
        raise ParityError(f"{context}: ticket is not a legal 6/49")
    return canonical


def _source_behavior_facts(
    frozen_source_directory: Path,
) -> dict[str, object]:
    ensemble = frozen_source_directory.joinpath(
        ENSEMBLE_METHOD_ID
    ).read_text(encoding="utf-8")
    backtest = frozen_source_directory.joinpath(
        BACKTEST_METHOD_ID
    ).read_text(encoding="utf-8")
    advanced = frozen_source_directory.joinpath(
        "lottery_api/models/advanced_strategies.py"
    ).read_text(encoding="utf-8")
    if any(
        fragment not in ensemble
        for fragment in (
            "random.seed(seed)",
            "np.random.seed(seed)",
            "def predict_3bets(self, history=None):",
            "return [bet1, bet2, bet3]",
            "ensemble = DiversifiedEnsemble()",
            "bets = ensemble.predict_3bets()",
        )
    ):
        raise ParityError("diversified ensemble frozen behavior changed")
    if any(
        fragment not in backtest
        for fragment in (
            "def run_backtest(n_periods=50, strategy='DIVERSIFIED', seed=123):",
            "random.seed(seed)",
            "np.random.seed(seed)",
            "ensemble = DiversifiedEnsemble(seed=seed)",
            "horizons = [150, 500]",
            "res_strat = run_backtest(h, strategy='DIVERSIFIED')",
            "res_rand = run_backtest(h, strategy='RANDOM')",
        )
    ):
        raise ParityError("diversified backtest frozen behavior changed")
    if (
        "數據不足，至少需要 50 期進行聚類分析"  # noqa: RUF001
        not in advanced
    ):
        raise ParityError("advanced clustering minimum changed")
    return {
        ENSEMBLE_METHOD_ID: {
            "entrypoint": "DiversifiedEnsemble.predict_3bets",
            "history_order_at_call": "RECENT_FIRST_THEN_SOURCE_SORTS_ASC",
            "minimum_history_draws": 50,
            "native_ticket_count": 3,
            "source_rng_reset": (
                "PYTHON_RANDOM_42_AND_NUMPY_RANDOM_42_PER_TARGET"
            ),
        },
        BACKTEST_METHOD_ID: {
            "entrypoint": "run_comprehensive_audit",
            "excluded_comparator": "predict_random_3bets",
            "horizon_order": [150, 500],
            "native_ticket_count_by_configuration_count": {
                "1": 3,
                "2": 6,
            },
            "source_rng_reset": (
                "PYTHON_RANDOM_123_AND_NUMPY_RANDOM_123_AT_EACH_"
                "DIVERSIFIED_HORIZON_START"
            ),
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
                "insufficient_history_reason": (
                    INSUFFICIENT_HISTORY_REASON
                ),
                "outside_horizon_reason": OUTSIDE_HORIZON_REASON,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
        env=environment,
    )
    if completed.returncode != 0:
        raise ParityError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "wave-62 frozen reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityError(
            "wave-62 frozen reference emitted invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityError("wave-62 frozen reference output changed")
    document = cast(dict[str, Any], parsed)
    if (
        document.get("python_version") != "3.9.6"
        or document.get("numpy_version") != "1.26.2"
        or document.get("scipy_version") != "1.12.0"
        or document.get("networkx_version") != "3.2.1"
    ):
        raise ParityError("wave-62 frozen reference runtime changed")
    return document


def verify_wave62_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the full ledger and frozen-source parity proof."""

    source_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=method_id,
            expected_sha256=SOURCE_SHA256_BY_METHOD[method_id],
        )
        for method_id in METHOD_IDS
    ]
    support_artifacts = [
        _artifact(
            frozen_root=frozen_root,
            frozen_source_directory=frozen_source_directory,
            path=path,
            expected_sha256=digest,
        )
        for path, digest in sorted(SUPPORT_ARTIFACTS.items())
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
        raise ParityError("wave-62 target set changed")
    draws: list[dict[str, object]] = [
        {
            "date": draw.draw_date.isoformat(),
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
            "special": draw.special,
        }
        for draw in pinned.draws
    ]
    reference = _reference_outputs(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=draws,
    )
    outputs_raw = reference.get("outputs")
    errors_raw = reference.get("errors")
    configurations_raw = reference.get("configuration_counts")
    if (
        not isinstance(outputs_raw, dict)
        or not isinstance(errors_raw, dict)
        or not isinstance(configurations_raw, dict)
    ):
        raise ParityError("wave-62 reference layout changed")
    outputs = cast(dict[str, object], outputs_raw)
    errors = cast(dict[str, object], errors_raw)
    configurations = cast(dict[str, object], configurations_raw)
    if (
        set(outputs) != set(METHOD_IDS)
        or set(errors) != set(METHOD_IDS)
        or set(configurations) != set(METHOD_IDS)
    ):
        raise ParityError("wave-62 reference method set changed")
    typed_outputs: dict[str, list[list[list[int]] | None]] = {}
    typed_errors: dict[str, list[str | None]] = {}
    typed_configurations: dict[str, list[int | None]] = {}
    status_counts: dict[str, dict[str, int]] = {}
    native_count_distribution: dict[str, dict[str, int]] = {}
    duplicate_count_distribution: dict[str, dict[str, int]] = {}
    sequence_sha256_by_method: dict[str, str] = {}
    native_ticket_case_count = 0
    for method_id in METHOD_IDS:
        rows_raw = outputs[method_id]
        reasons_raw = errors[method_id]
        configs_raw = configurations[method_id]
        if (
            not isinstance(rows_raw, list)
            or not isinstance(reasons_raw, list)
            or not isinstance(configs_raw, list)
        ):
            raise ParityError("wave-62 method sequence changed")
        rows = cast(list[object], rows_raw)
        reasons = cast(list[object], reasons_raw)
        configs = cast(list[object], configs_raw)
        if (
            len(rows) != 2149
            or len(reasons) != 2149
            or len(configs) != 2149
        ):
            raise ParityError("wave-62 target count changed")
        typed_rows: list[list[list[int]] | None] = []
        typed_reasons: list[str | None] = []
        typed_configs: list[int | None] = []
        method_statuses: dict[str, int] = {}
        method_native_counts: dict[str, int] = {}
        method_duplicate_counts: dict[str, int] = {}
        for index, (candidate, reason, configuration_count) in enumerate(
            zip(rows, reasons, configs, strict=True)
        ):
            if candidate is None:
                if not isinstance(reason, str) or configuration_count is not None:
                    raise ParityError("wave-62 closed output changed")
                status = (
                    "CLOSED_INSUFFICIENT_HISTORY"
                    if reason == INSUFFICIENT_HISTORY_REASON
                    else (
                        "CLOSED_REJECTED"
                        if reason == OUTSIDE_HORIZON_REASON
                        else "CLOSED_EXECUTION_ERROR"
                    )
                )
                method_statuses[status] = (
                    method_statuses.get(status, 0) + 1
                )
                typed_rows.append(None)
                typed_reasons.append(reason)
                typed_configs.append(None)
                continue
            if (
                reason is not None
                or type(configuration_count) is not int
                or not isinstance(candidate, list)
            ):
                raise ParityError("wave-62 executable output changed")
            portfolio = [
                _validate_ticket(
                    ticket,
                    context=(
                        f"{method_id} target {index} "
                        f"ticket {ticket_index}"
                    ),
                )
                for ticket_index, ticket in enumerate(
                    cast(list[object], candidate)
                )
            ]
            expected_count = 3 * configuration_count
            if (
                configuration_count not in {1, 2}
                or len(portfolio) != expected_count
                or (
                    method_id == ENSEMBLE_METHOD_ID
                    and configuration_count != 1
                )
            ):
                raise ParityError("wave-62 native ticket count changed")
            duplicates = len(portfolio) - len(
                {tuple(ticket) for ticket in portfolio}
            )
            method_statuses["OK"] = (
                method_statuses.get("OK", 0) + 1
            )
            method_native_counts[str(len(portfolio))] = (
                method_native_counts.get(str(len(portfolio)), 0) + 1
            )
            method_duplicate_counts[str(duplicates)] = (
                method_duplicate_counts.get(str(duplicates), 0) + 1
            )
            native_ticket_case_count += len(portfolio)
            typed_rows.append(portfolio)
            typed_reasons.append(None)
            typed_configs.append(configuration_count)
        typed_outputs[method_id] = typed_rows
        typed_errors[method_id] = typed_reasons
        typed_configurations[method_id] = typed_configs
        status_counts[method_id] = method_statuses
        native_count_distribution[method_id] = method_native_counts
        duplicate_count_distribution[method_id] = (
            method_duplicate_counts
        )
        sequence_sha256_by_method[method_id] = hashlib.sha256(
            _canonical_bytes(typed_rows)
        ).hexdigest()
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
        for index in range(2149)
    ]
    ledger: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "closed_reason_by_method": typed_errors,
        "configuration_count_by_method": typed_configurations,
        "context_numbers_sha256_by_target": context_sha256,
        "context_policy": CONTEXT_POLICY,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "source_sha256_by_method": SOURCE_SHA256_BY_METHOD,
        "target_draw_numbers": [
            draw.draw_number for draw in pinned.draws
        ],
        "tickets_by_method": typed_outputs,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    ledger_raw = _canonical_bytes(ledger) + b"\n"
    parity: dict[str, object] = {
        "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "ledger_file_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "native_duplicate_ticket_count_distribution_by_method": (
            duplicate_count_distribution
        ),
        "native_ticket_case_count": native_ticket_case_count,
        "native_ticket_count_distribution_by_method": (
            native_count_distribution
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
        "status": "PASS",
        "status_counts_by_method": status_counts,
        "support_artifacts": support_artifacts,
        "ticket_sequence_sha256_by_method": (
            sequence_sha256_by_method
        ),
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
            raise SystemExit(
                f"refusing to overwrite existing output: {path}"
            )
    ledger, parity = verify_wave62_parity(
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
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_raw
                ).hexdigest(),
                "native_ticket_case_count": parity[
                    "native_ticket_case_count"
                ],
                "output_file": str(args.output_file),
                "parity_file_sha256": hashlib.sha256(
                    parity_raw
                ).hexdigest(),
                "parity_sha256": parity["parity_sha256"],
                "status": parity["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
