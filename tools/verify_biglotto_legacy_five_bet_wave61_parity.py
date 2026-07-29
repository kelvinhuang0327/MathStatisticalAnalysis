#!/usr/bin/env python3
"""Freeze the source-declared closed-result five-bet portfolios."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
METHOD_ID = "tools/test_5bet_optimization.py"
SOURCE_SHA256 = (
    "987f6c374c0904ecadc91105db82d8887126a7c22ca0af08a10ac881753b8c4d"
)
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_FIVE_BET_WAVE61_TICKET_LEDGER_V1"
)
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_FIVE_BET_WAVE61_PARITY_V1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_SOURCE_CLOSED_RESULT_HORIZONS_150_200_SEED42_V1"
)
OUTSIDE_HORIZON_REASON = (
    "OUTSIDE_FROZEN_SOURCE_CLOSED_RESULT_HORIZONS_150_200"
)
REFERENCE_SCRIPT = r'''
import ast
import contextlib
import importlib.util
import io
import json
import sys
import types
from collections import defaultdict
from pathlib import Path

config = json.loads(sys.stdin.read())
root = Path(config["source_root"])
sys.path.insert(0, str(root / "lottery_api"))
sys.path.insert(0, str(root))
tools_package = types.ModuleType("tools")
tools_package.__path__ = [str(root / "tools")]
sys.modules["tools"] = tools_package
source_path = root / "tools/test_5bet_optimization.py"
spec = importlib.util.spec_from_file_location("wave61_five_bet", source_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

tree = ast.parse(source_path.read_text(encoding="utf-8"))
dense_node = None
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name == "predict_5bet_dense":
                dense_node = child
                break
if dense_node is None:
    raise RuntimeError("frozen dense selector not found")
dense_module = ast.Module(body=[dense_node], type_ignores=[])
ast.fix_missing_locations(dense_module)
exec(compile(dense_module, str(source_path), "exec"), module.__dict__)

draws = config["draws"]
rules = {
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,
    "lotteryType": "BIG_LOTTO",
}
opt = module.FiveBetOptimizer()
module.opt = opt
dense = module.__dict__["predict_5bet_dense"]
portfolios = defaultdict(list)
configuration_counts = defaultdict(int)
errors = {}

def run_config(label, function, periods):
    module.set_seed(42)
    for index in range(len(draws) - periods, len(draws)):
        history = draws[:index]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = function(history, rules)
            tickets = [bet["numbers"] for bet in result["bets"]]
            canonical = []
            for ticket in tickets:
                values = sorted(int(number) for number in ticket)
                if (
                    len(values) != 6
                    or len(set(values)) != 6
                    or values[0] < 1
                    or values[-1] > 49
                ):
                    raise RuntimeError(f"illegal ticket from {label}")
                canonical.append(values)
            portfolios[index].extend(canonical)
            configuration_counts[index] += 1
        except Exception as exc:
            errors[index] = f"{label}:{type(exc).__name__}:{exc}"

run_config("5ME_P150", opt.predict_5me, 150)
run_config("4P1_P150", opt.predict_4p1_tme_skew, 150)
run_config("5ME_P200", opt.predict_5me, 200)
run_config("4P1_P200", opt.predict_4p1_tme_skew, 200)
run_config("DENSE_P200", dense, 200)

tickets = []
reasons = []
configs = []
for index in range(len(draws)):
    if index < len(draws) - 200:
        tickets.append(None)
        reasons.append(config["outside_horizon_reason"])
        configs.append(None)
    elif index in errors:
        tickets.append(None)
        reasons.append("FROZEN_SOURCE_EXECUTION_ERROR:" + errors[index])
        configs.append(None)
    else:
        tickets.append(portfolios[index])
        reasons.append(None)
        configs.append(configuration_counts[index])

print(
    json.dumps(
        {
            "closed_reason": reasons,
            "local_configuration_count": configs,
            "targets": [draw["draw"] for draw in draws],
            "tickets": tickets,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
)
'''


class ParityVerificationError(ValueError):
    """Frozen wave-61 source or output violates its contract."""


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
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen Git query failed"
        )
    return completed.stdout


def _run_reference(
    *,
    reference_python: Path,
    frozen_source_directory: Path,
    draws: list[dict[str, object]],
) -> dict[str, Any]:
    completed = subprocess.run(
        (str(reference_python), "-c", REFERENCE_SCRIPT),
        input=_canonical_bytes(
            {
                "draws": draws,
                "outside_horizon_reason": OUTSIDE_HORIZON_REASON,
                "source_root": str(frozen_source_directory),
            }
        ),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityVerificationError(
            completed.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
            or "frozen five-bet reference execution failed"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParityVerificationError(
            "frozen five-bet reference output is invalid"
        ) from exc
    if not isinstance(parsed, dict):
        raise ParityVerificationError(
            "frozen five-bet reference output must be an object"
        )
    return cast(dict[str, Any], parsed)


def verify_wave61_parity(
    *,
    frozen_root: Path,
    frozen_source_directory: Path,
    database: Path,
    expected_database_sha256: str,
    reference_python: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Execute the frozen five-bet source and return checksummed output."""

    database_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    if database_sha256 != expected_database_sha256:
        raise ParityVerificationError(
            "physical regeneration database SHA changed"
        )
    frozen_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
    )
    extracted_raw = frozen_source_directory.joinpath(METHOD_ID).read_bytes()
    if (
        frozen_raw != extracted_raw
        or hashlib.sha256(frozen_raw).hexdigest() != SOURCE_SHA256
    ):
        raise ParityVerificationError("frozen source identity changed")
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
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
        for index in range(len(pinned.draws))
    ]
    reference = _run_reference(
        reference_python=reference_python,
        frozen_source_directory=frozen_source_directory,
        draws=[
            {
                "date": draw.draw_date.isoformat(),
                "draw": draw.draw_number,
                "numbers": list(draw.numbers),
                "special": draw.special,
            }
            for draw in pinned.draws
        ],
    )
    targets = cast(list[object], reference.get("targets", []))
    tickets = cast(list[object], reference.get("tickets", []))
    reasons = cast(
        list[object],
        reference.get("closed_reason", []),
    )
    configs = cast(
        list[object],
        reference.get("local_configuration_count", []),
    )
    if not (
        len(targets)
        == len(tickets)
        == len(reasons)
        == len(configs)
        == 2149
    ):
        raise ParityVerificationError("wave-61 coverage changed")
    status_counts: dict[str, int] = {}
    native_count_distribution: dict[str, int] = {}
    configuration_count_distribution: dict[str, int] = {}
    duplicate_count_distribution: dict[str, int] = {}
    native_ticket_case_count = 0
    for portfolio, reason, configuration_count in zip(
        tickets,
        reasons,
        configs,
        strict=True,
    ):
        if portfolio is None:
            if not isinstance(reason, str):
                raise ParityVerificationError(
                    "closed wave-61 target lacks a reason"
                )
            status_counts["CLOSED_REJECTED"] = (
                status_counts.get("CLOSED_REJECTED", 0) + 1
            )
            continue
        if (
            not isinstance(portfolio, list)
            or reason is not None
            or type(configuration_count) is not int
        ):
            raise ParityVerificationError(
                "executable wave-61 target changed"
            )
        typed_portfolio = cast(list[object], portfolio)
        native_count = len(typed_portfolio)
        if native_count not in {15, 25}:
            raise ParityVerificationError(
                "wave-61 native ticket count changed"
            )
        duplicates = native_count - len(
            {
                tuple(cast(list[int], ticket))
                for ticket in typed_portfolio
                if isinstance(ticket, list)
            }
        )
        status_counts["OK"] = status_counts.get("OK", 0) + 1
        native_count_distribution[str(native_count)] = (
            native_count_distribution.get(str(native_count), 0) + 1
        )
        configuration_count_distribution[
            str(configuration_count)
        ] = (
            configuration_count_distribution.get(
                str(configuration_count),
                0,
            )
            + 1
        )
        duplicate_count_distribution[str(duplicates)] = (
            duplicate_count_distribution.get(str(duplicates), 0) + 1
        )
        native_ticket_case_count += native_count
    ledger: dict[str, object] = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "closed_reason": reasons,
        "context_sha256": context_sha256,
        "dataset_sha256": PINNED_DATASET_SHA256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_schema_version": LEDGER_SCHEMA_VERSION,
        "legacy_method_id": METHOD_ID,
        "local_configuration_count": configs,
        "source_sha256": SOURCE_SHA256,
        "targets": targets,
        "tickets": tickets,
    }
    ledger["ledger_content_sha256"] = hashlib.sha256(
        _canonical_bytes(ledger)
    ).hexdigest()
    parity: dict[str, object] = {
        "causal_protocol": CAUSAL_PROTOCOL,
        "configuration_count_distribution": (
            configuration_count_distribution
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "database_physical_sha256": database_sha256,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "ledger_content_sha256": ledger["ledger_content_sha256"],
        "native_duplicate_ticket_count_distribution": (
            duplicate_count_distribution
        ),
        "native_ticket_case_count": native_ticket_case_count,
        "native_ticket_count_distribution": native_count_distribution,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifact": {
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{METHOD_ID}",
                )
                .decode("ascii")
                .strip()
            ),
            "source_byte_size": len(frozen_raw),
            "source_sha256": SOURCE_SHA256,
        },
        "source_reference_runtime": (
            "CPYTHON_3_9_6_NUMPY_1_26_2_SOURCE_RUN_BENCHMARK_SEED42"
        ),
        "status": "PASS",
        "status_counts": status_counts,
        "ticket_sequence_sha256": hashlib.sha256(
            _canonical_bytes(tickets)
        ).hexdigest(),
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
    ledger, parity = verify_wave61_parity(
        frozen_root=args.frozen_root,
        frozen_source_directory=args.frozen_source_directory,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
        reference_python=args.reference_python,
    )
    ledger_payload = _canonical_bytes(ledger) + b"\n"
    parity_payload = _canonical_bytes(parity) + b"\n"
    args.ledger_output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.ledger_output_file.write_bytes(ledger_payload)
    args.output_file.write_bytes(parity_payload)
    print(
        json.dumps(
            {
                "ledger_content_sha256": ledger[
                    "ledger_content_sha256"
                ],
                "ledger_file_sha256": hashlib.sha256(
                    ledger_payload
                ).hexdigest(),
                "native_ticket_case_count": parity[
                    "native_ticket_case_count"
                ],
                "output_file": str(args.output_file),
                "parity_file_sha256": hashlib.sha256(
                    parity_payload
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
