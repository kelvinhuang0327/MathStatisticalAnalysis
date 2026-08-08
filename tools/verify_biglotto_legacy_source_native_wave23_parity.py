#!/usr/bin/env python3
"""Verify wave-23 ports against frozen UnifiedPredictionEngine statements."""

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
from typing import Any, ClassVar, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    legacy_numpy_argsort,
)
from lottolab.application.legacy_source_native_portfolios_wave23 import (
    FIVE_ME_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD,
    SOURCE_NATIVE_WAVE23_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD,
    TME_METHOD_ID,
    LegacySourceNativeWave23Request,
    generate_legacy_source_native_wave23_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE23_PARITY_V1"
)
_HISTORY_COUNTS = (1, 3, 50, 149, 150, 2148)
_SUPPORT_PATH = "lottery_api/models/unified_predictor.py"
_FIVE_ME_ORDER = (
    "statistical_predict",
    "deviation_predict",
    "markov_predict",
    "hot_cold_mix_predict",
    "trend_predict",
)
_TME_ORDER = (
    "statistical_predict",
    "deviation_predict",
    "markov_predict",
)


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _Vector:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = list(values)

    def __iter__(self) -> Iterator[float]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int) -> float:
        return self._values[index]

    def __setitem__(self, index: int, value: float) -> None:
        self._values[index] = value

    def __iadd__(self, other: Iterable[float]) -> _Vector:
        for index, value in enumerate(other):
            self._values[index] += value
        return self

    def __truediv__(self, divisor: float) -> _Vector:
        return _Vector(value / divisor for value in self._values)

    def __mul__(self, multiplier: float) -> _Vector:
        return _Vector(value * multiplier for value in self._values)

    def copy(self) -> _Vector:
        return _Vector(self._values)


class _Matrix:
    def __init__(self, rows: Iterable[Iterable[float]]) -> None:
        self._rows = [list(row) for row in rows]

    def __getitem__(self, index: int) -> list[float]:
        return self._rows[index]

    def __mul__(self, multiplier: float) -> _Matrix:
        return _Matrix(
            [value * multiplier for value in row]
            for row in self._rows
        )

    def __truediv__(self, row_sums: list[float]) -> _Matrix:
        return _Matrix(
            [
                value / row_sums[row_index]
                for value in row
            ]
            for row_index, row in enumerate(self._rows)
        )

    def sum(
        self,
        *,
        axis: int,
        keepdims: bool,
    ) -> list[float]:
        if axis != 1 or keepdims is not True:
            raise ParityError("unexpected frozen matrix reduction")
        return [sum(row) for row in self._rows]


class _NumpySelectionCompat:
    ndarray = _Vector

    @staticmethod
    def argsort(values: _Vector) -> list[int]:
        return legacy_numpy_argsort(list(values))

    @staticmethod
    def clip(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def exp(value: float) -> float:
        return math.exp(value)

    @staticmethod
    def max(values: _Vector) -> float:
        return max(values)

    @staticmethod
    def mean(values: Iterable[float]) -> float:
        materialized = list(values)
        return sum(materialized) / len(materialized)

    @staticmethod
    def ones(shape: tuple[int, int]) -> _Matrix:
        rows, columns = shape
        return _Matrix(
            [1.0] * columns for _index in range(rows)
        )

    @staticmethod
    def power(value: float, exponent: float) -> float:
        return math.pow(value, exponent)

    @staticmethod
    def sqrt(value: float) -> float:
        return math.sqrt(value)

    @staticmethod
    def std(values: Iterable[float]) -> float:
        materialized = list(values)
        mean = sum(materialized) / len(materialized)
        return math.sqrt(
            sum((value - mean) ** 2 for value in materialized)
            / len(materialized)
        )

    @staticmethod
    def zeros(size: int) -> _Vector:
        return _Vector(0.0 for _index in range(size))


class _PinnedConfig:
    _VALUES: ClassVar[dict[str, object]] = {
        "strategies.BIG_LOTTO.trend.lambda": 0.01,
        "strategies.BIG_LOTTO.deviation.weights": {
            "frequency": 0.30,
            "zone": 0.25,
            "odd_even": 0.20,
            "high_low": 0.15,
            "gap": 0.10,
        },
        "strategies.BIG_LOTTO.statistical.params": {
            "sum_range_mult": 0.4,
            "ac_min_mult": 0.15,
            "ac_max_mult": 0.35,
            "odd_tolerance": 2,
            "spread_mult": 0.4,
            "unique_last_digits_min": 4,
            "weight_power": 0.5,
        },
    }

    def get(self, key: str, default: object = None) -> object:
        return self._VALUES.get(key, default)


def _ignore_log(*_args: object) -> None:
    return None


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


def _selection_assignment(
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
                value=ast.Name(id=return_name, ctx=ast.Load())
            ),
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
        type_params=[],
    )


def _selection_markov(method: ast.FunctionDef) -> ast.FunctionDef:
    end: int | None = None
    for index, node in enumerate(method.body):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "predicted_numbers"
            and node.value.func.attr == "sort"
        ):
            end = index
            break
    if end is None:
        raise ParityError("frozen markov selection statements changed")
    return ast.FunctionDef(
        name=method.name,
        args=method.args,
        body=[
            *method.body[: end + 1],
            ast.Return(
                value=ast.Name(
                    id="predicted_numbers", ctx=ast.Load()
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
        "_calculate_markov_stability",
        "_detect_hot_cold_transitions",
        "_find_optimal_markov_order",
        "_get_strategy_config",
        "_markov_order1",
        "_markov_order2",
        "_markov_order3",
        "_multi_window_temperature_analysis",
        "deviation_predict",
        "filter_by_global_constraints",
        "hot_cold_mix_predict",
        "markov_predict",
        "statistical_predict",
        "trend_predict",
    }
    if not required.issubset(methods):
        raise ParityError("frozen wave-23 engine methods are missing")
    selected_class = ast.ClassDef(
        name="_FrozenWave23Engine",
        bases=[],
        keywords=[],
        body=[
            methods["_get_strategy_config"],
            methods["filter_by_global_constraints"],
            _selection_assignment(
                methods["trend_predict"],
                terminal_assignment="predicted_numbers",
                return_name="predicted_numbers",
            ),
            _selection_assignment(
                methods["deviation_predict"],
                terminal_assignment="predicted_numbers",
                return_name="predicted_numbers",
            ),
            _selection_markov(methods["markov_predict"]),
            methods["_find_optimal_markov_order"],
            methods["_calculate_markov_stability"],
            methods["_markov_order1"],
            methods["_markov_order2"],
            methods["_markov_order3"],
            _selection_assignment(
                methods["hot_cold_mix_predict"],
                terminal_assignment="predicted",
                return_name="predicted",
            ),
            methods["_multi_window_temperature_analysis"],
            methods["_detect_hot_cold_transitions"],
            _selection_assignment(
                methods["statistical_predict"],
                terminal_assignment="predicted_numbers",
                return_name="predicted_numbers",
            ),
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
        "log_data_range": _ignore_log,
        "np": _NumpySelectionCompat,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["_FrozenWave23Engine"]


def _declared_method_order(source_text: str) -> tuple[str, ...]:
    tree = ast.parse(source_text)
    found: list[tuple[str, ...]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "methods"
            for target in node.targets
        ):
            value = cast(object, ast.literal_eval(node.value))
            if isinstance(value, list):
                items = cast(list[object], value)
                if all(isinstance(item, str) for item in items):
                    found.append(tuple(cast(list[str], items)))
    if len(found) != 1:
        raise ParityError("frozen source method order changed")
    return found[0]


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
        for draw, draw_date in zip(history, dates, strict=True)
    ]


def _compare_case(
    *,
    engine_class: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
    dates: tuple[str, ...],
    method_id: str,
    method_order: tuple[str, ...],
    target_draw_number: str,
) -> dict[str, object]:
    source = engine_class()
    source.config = _PinnedConfig()
    rules = {
        "hasSpecialNumber": False,
        "maxNumber": 49,
        "minNumber": 1,
        "name": "BIG_LOTTO",
        "pickCount": 6,
    }
    source_history = _source_history(history, dates)
    source_tickets = [
        getattr(source, method_name)(source_history, rules)
        for method_name in method_order
    ]
    port = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=method_id,
            target_draw_number=target_draw_number,
            history=history,
        )
    )
    port_tickets = [list(ticket) for ticket in port.tickets]
    if source_tickets != port_tickets:
        raise ParityError(
            f"ticket parity failed for {method_id} at {target_draw_number}"
        )
    return {
        "history_draw_count": len(history),
        "legacy_method_id": method_id,
        "markov_order": port.metadata.markov_order,
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
        require_replay_authority=False,
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    all_dates = tuple(draw.draw_date.isoformat() for draw in pinned.draws)
    declared_orders: dict[str, tuple[str, ...]] = {}
    source_artifacts: list[dict[str, object]] = []
    for method_id, expected_order in (
        (FIVE_ME_METHOD_ID, _FIVE_ME_ORDER),
        (TME_METHOD_ID, _TME_ORDER),
    ):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        if hashlib.sha256(raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE23_METHOD[method_id]
        ):
            raise ParityError("frozen source SHA changed")
        declared_order = _declared_method_order(
            raw.decode("utf-8")
        )
        if declared_order != expected_order:
            raise ParityError("frozen source positional order changed")
        declared_orders[method_id] = declared_order
        source_artifacts.append(
            {
                "path": method_id,
                "source_blob_id": _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{method_id}",
                )
                .decode("utf-8")
                .strip(),
                "source_byte_size": len(raw),
                "source_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    support_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    if hashlib.sha256(support_raw).hexdigest() != (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD[
            FIVE_ME_METHOD_ID
        ][0][1]
    ):
        raise ParityError("frozen UnifiedPredictionEngine SHA changed")
    for method_id in (FIVE_ME_METHOD_ID, TME_METHOD_ID):
        for path, expected_sha256 in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE23_METHOD[
                method_id
            ]
        ):
            raw = _git(
                frozen_root,
                "show",
                f"{FROZEN_SOURCE_COMMIT}:{path}",
            )
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise ParityError(
                    f"frozen support SHA changed: {path}"
                )
    engine_class = _load_frozen_engine(
        support_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    cases = [
        _compare_case(
            engine_class=engine_class,
            history=all_history[:count],
            dates=all_dates[:count],
            method_id=method_id,
            method_order=declared_orders[method_id],
            target_draw_number=f"parity-{method_id}-{count}",
        )
        for count in _HISTORY_COUNTS
        for method_id in (FIVE_ME_METHOD_ID, TME_METHOD_ID)
    ]
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_FIVE_UNIFIED_SELECTION_PATHS_WITH_"
            "PINNED_BIG_LOTTO_CONFIG_AND_NUMPY_SELECTION_COMPAT"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE23_PROTOCOL,
        "source_artifacts": source_artifacts,
        "status": "PASS",
        "support_artifact": {
            "path": _SUPPORT_PATH,
            "source_blob_id": _git(
                frozen_root,
                "rev-parse",
                f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
            )
            .decode("utf-8")
            .strip(),
            "source_byte_size": len(support_raw),
            "source_sha256": hashlib.sha256(support_raw).hexdigest(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-repository",
        required=True,
        type=Path,
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--expected-database-sha256",
        required=True,
    )
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(
            f"refusing to overwrite existing output: {args.output_file}"
        )
    result = verify_parity(
        frozen_root=args.legacy_repository,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(result) + b"\n"
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": hashlib.sha256(payload).hexdigest(),
                "status": result["status"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
