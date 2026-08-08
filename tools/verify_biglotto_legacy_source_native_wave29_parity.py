#!/usr/bin/env python3
"""Verify wave-29 ports against the frozen rolling Elite-7 AST sources."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import random
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave29 import (
    ELITE_CLAIM_VERIFIER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    OPTIMIZED_BACKTEST_METHOD_ID,
    SOURCE_NATIVE_WAVE29_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS,
    LegacySourceNativeWave29Request,
    frozen_wave29_engine_output,
    generate_legacy_source_native_wave29_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE29_PARITY_V1"
)
_HISTORY_COUNTS = (*range(1, 61), 100, 101, 110, 200, 2148)
_ENTRYPOINT_BY_METHOD = {
    OPTIMIZED_BACKTEST_METHOD_ID: "backtest_optimized_7bet",
    ELITE_CLAIM_VERIFIER_METHOD_ID: "backtest_elite7",
}


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


def _instrument_entrypoint(
    source_text: str,
    *,
    method_id: str,
) -> tuple[ast.FunctionDef, dict[str, object]]:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    function_name = _ENTRYPOINT_BY_METHOD[method_id]
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == function_name
    ]
    if len(matches) != 1:
        raise ParityError(f"frozen entrypoint changed: {method_id}")
    function = matches[0]
    if method_id == OPTIMIZED_BACKTEST_METHOD_ID:
        periods = [
            node
            for node in function.body
            if _is_name_assignment(node, "test_periods")
        ]
        if (
            len(periods) != 1
            or not isinstance(periods[0], ast.Assign)
        ):
            raise ParityError("optimized test-period harness changed")
        periods[0].value = ast.Constant(value=1)
    top_loops = [
        node
        for node in function.body
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "i"
    ]
    if len(top_loops) != 1:
        raise ParityError(f"frozen rolling loop changed: {method_id}")
    loop = top_loops[0]
    marker = (
        "period_win"
        if method_id == OPTIMIZED_BACKTEST_METHOD_ID
        else "period_match3"
    )
    insertion_points = [
        index
        for index, node in enumerate(loop.body)
        if _is_name_assignment(node, marker)
    ]
    if len(insertion_points) != 1:
        raise ParityError(f"frozen capture point changed: {method_id}")
    loop.body.insert(
        insertion_points[0],
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_capture_bets", ctx=ast.Load()),
                args=[ast.Name(id="bets", ctx=ast.Load())],
                keywords=[],
            )
        ),
    )
    random_sample_calls = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "random"
        and node.func.attr == "sample"
    )
    return function, {
        "all_base_methods_failed_behavior": (
            "UNSEEDED_RANDOM_FALLBACK"
            if random_sample_calls == 1
            else "NO_CONSENSUS_TICKET"
        ),
        "random_sample_fallback_call_count": random_sample_calls,
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
                frozen_wave29_engine_output(method_name, converted)
            )
        }

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("deviation", history)

    def markov_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("markov", history)

    def statistical_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("statistical", history)


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
    def __init__(
        self,
        *,
        method_id: str,
        function: object,
        namespace: dict[str, object],
    ) -> None:
        self._method_id = method_id
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
        rules = {"minNumber": 1, "maxNumber": 49, "pickCount": 6}
        with contextlib.redirect_stdout(io.StringIO()):
            if self._method_id == OPTIMIZED_BACKTEST_METHOD_ID:
                cast(Any, self._function)()
            else:
                cast(Any, self._function)(chronological, rules, 1)
        if len(captures) != 1:
            raise ParityError("frozen source capture count changed")
        raw_bets = cast(list[object], captures[0])
        if self._method_id == OPTIMIZED_BACKTEST_METHOD_ID:
            rows = [
                cast(set[int], cast(tuple[object, object], row)[1])
                for row in raw_bets
            ]
        else:
            rows = [cast(set[int], row) for row in raw_bets]
        return tuple(tuple(sorted(row)) for row in rows)


def _compile_entrypoint(
    source_text: str,
    *,
    method_id: str,
) -> tuple[_ReferenceEntrypoint, dict[str, object]]:
    function, facts = _instrument_entrypoint(
        source_text,
        method_id=method_id,
    )
    namespace: dict[str, object] = {
        "Counter": Counter,
        "UnifiedPredictionEngine": _FrozenEngineReference,
        "get_lottery_rules": _get_rules,
        "os": __import__("os"),
        "project_root": "/frozen",
        "random": random,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[function], type_ignores=[])
            ),
            filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            mode="exec",
        ),
        namespace,
    )
    return (
        _ReferenceEntrypoint(
            method_id=method_id,
            function=namespace[_ENTRYPOINT_BY_METHOD[method_id]],
            namespace=namespace,
        ),
        facts,
    )


def _get_rules(_lottery_type: object) -> dict[str, int]:
    return {"maxNumber": 49, "minNumber": 1, "pickCount": 6}


def verify_wave29_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute instrumented frozen AST entrypoints and compare port rows."""

    source_artifacts: list[dict[str, str]] = []
    entrypoints: dict[str, _ReferenceEntrypoint] = {}
    behavior_facts: dict[str, dict[str, object]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        source = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        digest = hashlib.sha256(source).hexdigest()
        if (
            digest
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        entrypoint, facts = _compile_entrypoint(
            source.decode("utf-8"),
            method_id=method_id,
        )
        entrypoints[method_id] = entrypoint
        behavior_facts[method_id] = facts
        source_artifacts.append({"path": method_id, "sha256": digest})
    expected_facts = {
        OPTIMIZED_BACKTEST_METHOD_ID: {
            "all_base_methods_failed_behavior": "UNSEEDED_RANDOM_FALLBACK",
            "random_sample_fallback_call_count": 1,
        },
        ELITE_CLAIM_VERIFIER_METHOD_ID: {
            "all_base_methods_failed_behavior": "NO_CONSENSUS_TICKET",
            "random_sample_fallback_call_count": 0,
        },
    }
    if behavior_facts != expected_facts:
        raise ParityError("frozen all-methods-failed branches changed")

    support_by_path = {
        path: expected_sha256
        for artifacts in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD.values()
        )
        for path, expected_sha256 in artifacts
    }
    support_artifacts: list[dict[str, str]] = []
    for path, expected_sha256 in sorted(support_by_path.items()):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ParityError(f"frozen support SHA changed: {path}")
        support_artifacts.append({"path": path, "sha256": digest})

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
    cases: list[dict[str, object]] = []
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target_draw_number = (
            pinned.draws[history_count].draw_number
            if history_count < len(pinned.draws)
            else f"AFTER_{history[-1].draw_number}"
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
            reference = entrypoints[method_id](history)
            port = generate_legacy_source_native_wave29_portfolio(
                LegacySourceNativeWave29Request(
                    legacy_method_id=method_id,
                    target_draw_number=target_draw_number,
                    history=history,
                )
            )
            if port.tickets != reference:
                raise ParityError(
                    f"output differs: {method_id}:{history_count}"
                )
            cases.append(
                {
                    "history_draw_count": history_count,
                    "legacy_method_id": method_id,
                    "native_duplicate_ticket_count": (
                        port.metadata.native_duplicate_ticket_count
                    ),
                    "native_ticket_count": len(port.tickets),
                    "status": "PASS",
                    "tickets": [
                        list(ticket) for ticket in port.tickets
                    ],
                }
            )
    return {
        "case_count": len(cases),
        "cases": cases,
        "closed_parity_case_count": 0,
        "database_sha256": pinned.database_sha256_before,
        "frozen_source_behavior_facts": behavior_facts,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_instrumentation": (
            "AST_CAPTURE_INSERTED_AFTER_SOURCE_PORTFOLIO_CONSTRUCTION_"
            "BEFORE_OUTCOME_SCORING"
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_native_protocol": SOURCE_NATIVE_WAVE29_PROTOCOL,
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
    result = verify_wave29_parity(
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
