#!/usr/bin/env python3
"""Verify wave-30 port against the frozen ten-bet AST source."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import math
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave30 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD,
    SOURCE_NATIVE_WAVE30_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD,
    TEN_BET_METHOD_ID,
    LegacySourceNativeWave30Request,
    frozen_wave30_engine_output,
    generate_legacy_source_native_wave30_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE30_PARITY_V1"
)
_HISTORY_COUNTS = (*range(1, 61), 100, 150, 200, 500, 2148)


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


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


def _is_name_assignment(node: ast.stmt, name: str) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    )


def _instrument_main(source_text: str) -> tuple[ast.FunctionDef, dict[str, int]]:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{TEN_BET_METHOD_ID}",
    )
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    if len(matches) != 1:
        raise ParityError("frozen ten-bet entrypoint changed")
    function = matches[0]
    period_assignments = [
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Tuple)
        and any(
            isinstance(element, ast.Name) and element.id == "periods"
            for element in node.targets[0].elts
        )
    ]
    if (
        len(period_assignments) != 1
        or not isinstance(period_assignments[0].value, ast.Tuple)
        or len(period_assignments[0].value.elts) != 3
    ):
        raise ParityError("frozen ten-bet periods harness changed")
    period_assignments[0].value.elts[0] = ast.Constant(value=1)
    loops = [
        node
        for node in function.body
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "i"
    ]
    if len(loops) != 1:
        raise ParityError("frozen ten-bet rolling loop changed")
    loop = loops[0]
    numpy_import_indices = [
        index
        for index, node in enumerate(loop.body)
        if isinstance(node, ast.Import)
        and any(alias.name == "numpy" for alias in node.names)
    ]
    if len(numpy_import_indices) != 1:
        raise ParityError("frozen scalar NumPy import changed")
    del loop.body[numpy_import_indices[0]]
    insertion_points = [
        index
        for index, node in enumerate(loop.body)
        if _is_name_assignment(node, "best_match")
    ]
    if len(insertion_points) != 1:
        raise ParityError("frozen ten-bet capture point changed")
    loop.body.insert(
        insertion_points[0],
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_capture_bets", ctx=ast.Load()),
                args=[
                    ast.Subscript(
                        value=ast.Name(id="bets", ctx=ast.Load()),
                        slice=ast.Slice(
                            lower=None,
                            upper=ast.Constant(value=10),
                            step=None,
                        ),
                        ctx=ast.Load(),
                    )
                ],
                keywords=[],
            )
        ),
    )
    scalar_exp_calls = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "np"
        and node.func.attr == "exp"
        and len(node.args) == 1
    )
    return function, {
        "removed_local_numpy_import_count": 1,
        "scalar_numpy_exp_call_site_count": scalar_exp_calls,
    }


class _FrozenEngineReference:
    @staticmethod
    def _result(
        method_name: str,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        converted = tuple(
            LegacyHistoryDraw(
                draw_number=cast(str, row["draw_number"]),
                numbers=cast(
                    tuple[int, int, int, int, int, int],
                    row["numbers"],
                ),
            )
            for row in history
        )
        return {
            "numbers": list(
                frozen_wave30_engine_output(method_name, converted)
            )
        }

    def markov_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("markov", history)

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("deviation", history)

    def statistical_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("statistical", history)

    def trend_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("trend", history)

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("frequency", history)

    def bayesian_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("bayesian", history)

    def hot_cold_mix_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("hot_cold_mix", history)


class _ScalarNumpyReference:
    @staticmethod
    def exp(value: float) -> float:
        return math.exp(value)


class _FakeDatabase:
    def __init__(self, chronological: list[dict[str, object]]) -> None:
        self._chronological = chronological

    def get_all_draws(
        self,
        *,
        lottery_type: str,
    ) -> list[dict[str, object]]:
        if lottery_type != "BIG_LOTTO":
            raise ParityError("frozen lottery type changed")
        return list(reversed(self._chronological))


class _DatabaseFactory:
    def __init__(self, chronological: list[dict[str, object]]) -> None:
        self._chronological = chronological

    def __call__(self, **_kwargs: object) -> _FakeDatabase:
        return _FakeDatabase(self._chronological)


class _ReferenceEntrypoint:
    def __init__(self, function: object, namespace: dict[str, object]) -> None:
        self._function = function
        self._namespace = namespace

    def __call__(
        self,
        history: tuple[LegacyHistoryDraw, ...],
    ) -> tuple[tuple[int, ...], ...]:
        chronological: list[dict[str, object]] = [
            {
                "date": f"FROZEN-{draw.draw_number}",
                "draw": draw.draw_number,
                "draw_number": draw.draw_number,
                "numbers": draw.numbers,
            }
            for draw in history
        ]
        chronological.append(
            {
                "date": "FROZEN-TARGET",
                "draw": "TARGET",
                "draw_number": "TARGET",
                "numbers": (1, 2, 3, 4, 5, 6),
            }
        )
        captures: list[object] = []

        def capture_bets(value: object) -> None:
            captures.append(value)

        self._namespace["_capture_bets"] = capture_bets
        self._namespace["DatabaseManager"] = _DatabaseFactory(chronological)
        with contextlib.redirect_stdout(io.StringIO()):
            cast(Any, self._function)()
        if len(captures) != 1:
            raise ParityError("frozen source capture count changed")
        rows = cast(list[list[int]], captures[0])
        return tuple(tuple(sorted(row)) for row in rows)


def _get_rules(_lottery_type: object) -> dict[str, int | str]:
    return {
        "maxNumber": 49,
        "minNumber": 1,
        "name": "BIG_LOTTO",
        "pickCount": 6,
    }


def _compile_entrypoint(
    source_text: str,
) -> tuple[_ReferenceEntrypoint, dict[str, int]]:
    function, facts = _instrument_main(source_text)
    namespace: dict[str, object] = {
        "Counter": Counter,
        "UnifiedPredictionEngine": _FrozenEngineReference,
        "get_lottery_rules": _get_rules,
        "np": _ScalarNumpyReference,
        "os": os,
        "project_root": "/frozen",
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[function], type_ignores=[])
            ),
            filename=f"{FROZEN_SOURCE_COMMIT}:{TEN_BET_METHOD_ID}",
            mode="exec",
        ),
        namespace,
    )
    return _ReferenceEntrypoint(namespace["main"], namespace), facts


def verify_wave30_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute instrumented frozen AST entrypoint and compare port rows."""

    source = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{TEN_BET_METHOD_ID}",
    )
    source_digest = hashlib.sha256(source).hexdigest()
    if (
        source_digest
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE30_METHOD[TEN_BET_METHOD_ID]
    ):
        raise ParityError("frozen source SHA changed")
    entrypoint, instrumentation_facts = _compile_entrypoint(
        source.decode("utf-8")
    )
    if instrumentation_facts != {
        "removed_local_numpy_import_count": 1,
        "scalar_numpy_exp_call_site_count": 1,
    }:
        raise ParityError("frozen scalar NumPy call surface changed")

    support_artifacts: list[dict[str, str]] = []
    requirements_pin_found = False
    for path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE30_METHOD[
            TEN_BET_METHOD_ID
        ]
    ):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ParityError(f"frozen support SHA changed: {path}")
        if path == "lottery_api/requirements.txt":
            requirements_pin_found = (
                "numpy==1.26.2" in raw.decode("utf-8").splitlines()
            )
        support_artifacts.append({"path": path, "sha256": digest})
    if not requirements_pin_found:
        raise ParityError("frozen NumPy version pin changed")

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
    cases: list[dict[str, object]] = []
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target_draw_number = (
            pinned.draws[history_count].draw_number
            if history_count < len(pinned.draws)
            else f"AFTER_{history[-1].draw_number}"
        )
        reference = entrypoint(history)
        port = generate_legacy_source_native_wave30_portfolio(
            LegacySourceNativeWave30Request(
                legacy_method_id=TEN_BET_METHOD_ID,
                target_draw_number=target_draw_number,
                history=history,
            )
        )
        if port.tickets != reference:
            raise ParityError(f"output differs: {history_count}")
        cases.append(
            {
                "history_draw_count": history_count,
                "legacy_method_id": TEN_BET_METHOD_ID,
                "native_duplicate_ticket_count": (
                    port.metadata.native_duplicate_ticket_count
                ),
                "native_ticket_count": len(port.tickets),
                "status": "PASS",
                "tickets": [list(ticket) for ticket in port.tickets],
            }
        )
    return {
        "case_count": len(cases),
        "cases": cases,
        "closed_parity_case_count": 0,
        "database_sha256": pinned.database_sha256_before,
        "frozen_numpy_version_pin": "numpy==1.26.2",
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "numpy_scalar_exp_instrumentation_facts": instrumentation_facts,
        "parity_instrumentation": (
            "AST_CAPTURE_AFTER_TEN_SOURCE_TICKETS_BEFORE_OUTCOME_SCORING_"
            "WITH_LOCAL_NUMPY_IMPORT_REPLACED_BY_SCALAR_MATH_EXP_SHIM"
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": [
            {"path": TEN_BET_METHOD_ID, "sha256": source_digest}
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE30_PROTOCOL,
        "status": "PASS",
        "support_artifacts": support_artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_wave30_parity(
        frozen_root=args.frozen_root,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    payload = _canonical_bytes(result) + b"\n"
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "closed_parity_case_count": (
                    result["closed_parity_case_count"]
                ),
                "output": str(args.output),
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
