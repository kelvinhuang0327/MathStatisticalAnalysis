#!/usr/bin/env python3
"""Verify wave-22 port against frozen true-frequency/deviation methods."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave22 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD,
    SMART_2BET_METHOD_ID,
    SOURCE_NATIVE_WAVE22_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD,
    LegacySourceNativeWave22Request,
    generate_legacy_source_native_wave22_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE22_PARITY_V1"
)
_HISTORY_COUNTS = (1, 3, 50, 200, 1000, 2148)
_SUPPORT_PATH = "lottery_api/models/unified_predictor.py"


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _Array:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = list(values)

    def __iter__(self) -> Iterator[float]:
        return iter(self._values)

    def __getitem__(self, index: int) -> float:
        return self._values[index]

    def __setitem__(self, index: int, value: float) -> None:
        self._values[index] = value

    def copy(self) -> _Array:
        return _Array(self._values)

    def __truediv__(self, divisor: float) -> _Array:
        return _Array(value / divisor for value in self._values)

    def __mul__(self, multiplier: float) -> _Array:
        return _Array(value * multiplier for value in self._values)


class _NumpySelectionCompat:
    @staticmethod
    def zeros(size: int) -> _Array:
        return _Array(0.0 for _index in range(size))

    @staticmethod
    def sqrt(value: float) -> float:
        return math.sqrt(value)

    @staticmethod
    def max(values: _Array) -> float:
        return max(values)


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
        raise ParityError("cannot read frozen source artifact")
    return completed.stdout


def _assigned_name(node: ast.stmt) -> str | None:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    return target.id if isinstance(target, ast.Name) else None


def _selection_method(
    method: ast.FunctionDef,
    *,
    terminal_assignment: str,
    return_name: str,
) -> ast.FunctionDef:
    end = next(
        (
            index
            for index, node in enumerate(method.body)
            if _assigned_name(node) == terminal_assignment
        ),
        None,
    )
    if end is None:
        raise ParityError(
            f"frozen {method.name} selection statements changed"
        )
    return ast.FunctionDef(
        name=method.name,
        args=method.args,
        body=[
            *method.body[: end + 1],
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="sorted", ctx=ast.Load()),
                    args=[
                        ast.Name(id=return_name, ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            ),
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
        type_params=[],
    )


def _load_frozen_engine(
    source_text: str,
    source_identity: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "UnifiedPredictionEngine"
    ]
    if len(classes) != 1:
        raise ParityError("frozen prediction engine class is missing")
    methods = {
        node.name: node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef)
    }
    required = {
        "_get_strategy_config",
        "deviation_predict",
        "true_frequency_predict",
    }
    if not required.issubset(methods):
        raise ParityError("frozen smart two-bet methods are missing")
    deviation = _selection_method(
        methods["deviation_predict"],
        terminal_assignment="predicted_numbers",
        return_name="predicted_numbers",
    )
    true_frequency = _selection_method(
        methods["true_frequency_predict"],
        terminal_assignment="top_nums",
        return_name="top_nums",
    )
    selected_class = ast.ClassDef(
        name="_FrozenSmartTwoBetEngine",
        bases=[],
        keywords=[],
        body=[
            methods["_get_strategy_config"],
            deviation,
            true_frequency,
        ],
        decorator_list=[],
        type_params=[],
    )
    module = ast.Module(body=[selected_class], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Any": Any,
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "__builtins__": __builtins__,
        "defaultdict": defaultdict,
        "np": _NumpySelectionCompat,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["_FrozenSmartTwoBetEngine"]


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
    dates: tuple[str, ...],
) -> list[dict[str, object]]:
    return [
        {
            "date": draw_date,
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw, draw_date in reversed(
            tuple(zip(history, dates, strict=True))
        )
    ]


def _compare_case(
    *,
    engine_class: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
    dates: tuple[str, ...],
    target_draw_number: str,
) -> dict[str, object]:
    source_history = _source_history(history, dates)
    source = engine_class()
    rules = {
        "frequency_window": 50,
        "maxNumber": 49,
        "minNumber": 1,
        "name": "BIG_LOTTO",
        "pickCount": 6,
    }
    source_tickets = [
        source.true_frequency_predict(source_history, rules),
        source.deviation_predict(source_history, rules),
    ]
    port = generate_legacy_source_native_wave22_portfolio(
        LegacySourceNativeWave22Request(
            legacy_method_id=SMART_2BET_METHOD_ID,
            target_draw_number=target_draw_number,
            history=history,
        )
    )
    port_tickets = [list(ticket) for ticket in port.tickets]
    if source_tickets != port_tickets:
        raise ParityError(
            f"ticket parity failed at {target_draw_number}"
        )
    return {
        "history_draw_count": len(history),
        "legacy_method_id": SMART_2BET_METHOD_ID,
        "native_duplicate_ticket_count": (
            port.metadata.native_duplicate_ticket_count
        ),
        "native_ticket_count": len(port_tickets),
        "ticket_sha256": hashlib.sha256(
            _canonical_bytes(port_tickets)
        ).hexdigest(),
    }


def verify_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    pinned = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=expected_database_sha256,
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    all_dates = tuple(draw.draw_date.isoformat() for draw in pinned.draws)
    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{SMART_2BET_METHOD_ID}",
    )
    expected_source_sha = (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE22_METHOD[
            SMART_2BET_METHOD_ID
        ]
    )
    if hashlib.sha256(source_raw).hexdigest() != expected_source_sha:
        raise ParityError("frozen source SHA changed")
    support_expected = (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD[
            SMART_2BET_METHOD_ID
        ][0][1]
    )
    support_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    if hashlib.sha256(support_raw).hexdigest() != support_expected:
        raise ParityError("frozen support source SHA changed")
    engine_class = _load_frozen_engine(
        support_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    cases = [
        _compare_case(
            engine_class=engine_class,
            history=all_history[:count],
            dates=all_dates[:count],
            target_draw_number=f"parity-after-{count}",
        )
        for count in _HISTORY_COUNTS
    ]
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_TRUE_FREQUENCY_AND_DEVIATION_"
            "SELECTION_STATEMENTS_WITH_NUMPY_SELECTION_COMPAT"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE22_PROTOCOL,
        "source_artifact": {
            "path": SMART_2BET_METHOD_ID,
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{SMART_2BET_METHOD_ID}",
                )
                .decode("ascii")
                .strip()
            ),
            "source_byte_size": len(source_raw),
            "source_sha256": expected_source_sha,
        },
        "status": "PASS",
        "support_artifacts": [
            {
                "path": path,
                "source_blob_id": (
                    _git(
                        frozen_root,
                        "rev-parse",
                        f"{FROZEN_SOURCE_COMMIT}:{path}",
                    )
                    .decode("ascii")
                    .strip()
                ),
                "source_byte_size": len(
                    _git(
                        frozen_root,
                        "show",
                        f"{FROZEN_SOURCE_COMMIT}:{path}",
                    )
                ),
                "source_sha256": expected_sha,
            }
            for path, expected_sha in (
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE22_METHOD[
                    SMART_2BET_METHOD_ID
                ]
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    document = verify_parity(
        frozen_root=args.frozen_root,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(document) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": document["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": hashlib.sha256(payload).hexdigest(),
                "status": document["status"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
