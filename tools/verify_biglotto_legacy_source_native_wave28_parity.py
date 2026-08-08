#!/usr/bin/env python3
"""Verify wave-28 ports against the frozen weighted and Elite-7 AST sources."""

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
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave28 import (
    ELITE_SEVEN_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SEVEN_BET_METHOD_ID,
    SOURCE_NATIVE_WAVE28_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS,
    TWO_BET_METHOD_ID,
    LegacySourceNativeWave28Request,
    LegacySourceNativeWave28SourceError,
    frozen_wave28_engine_output,
    generate_legacy_source_native_wave28_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE28_PARITY_V1"
)
_HISTORY_COUNTS = (
    *range(1, 61),
    68,
    76,
    78,
    82,
    100,
    101,
    110,
    192,
    200,
    2148,
)
_CLASS_ENTRYPOINTS = {
    TWO_BET_METHOD_ID: ("BigLotto2BetOptimizer", "predict_2bets"),
    SEVEN_BET_METHOD_ID: (
        "BigLotto7BetOptimizer",
        "predict_7bets_diversified",
    ),
}
_ASSIGNMENTS_BY_METHOD = {
    TWO_BET_METHOD_ID: {"PREDICTION_METHODS", "BET_SLICES_2"},
    SEVEN_BET_METHOD_ID: {"PREDICTION_METHODS", "BET_SLICES_7"},
}
_NEGATIVE_SELECTOR_PATH = "tools/negative_selector.py"


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


def _assignment_name(node: ast.stmt) -> str | None:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id
    return None


def _compile_negative_selector(source_text: str) -> type[object]:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{_NEGATIVE_SELECTOR_PATH}",
    )
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "NegativeSelector"
    ]
    if len(matches) != 1:
        raise ParityError("frozen NegativeSelector entrypoint changed")
    namespace: dict[str, object] = {
        "Counter": Counter,
        "__name__": "frozen_negative_selector_reference",
        "math": math,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=cast(list[ast.stmt], matches),
                    type_ignores=[],
                )
            ),
            filename=f"{FROZEN_SOURCE_COMMIT}:{_NEGATIVE_SELECTOR_PATH}",
            mode="exec",
        ),
        namespace,
    )
    return cast(type[object], namespace["NegativeSelector"])


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
                frozen_wave28_engine_output(method_name, converted)
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

    def zone_balance_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("zone_balance", history)

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("frequency", history)


def _compile_weighted_entrypoint(
    source_text: str,
    *,
    method_id: str,
    selector_class: type[object],
) -> object:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    class_name, method_name = _CLASS_ENTRYPOINTS[method_id]
    assignments = _ASSIGNMENTS_BY_METHOD[method_id]
    body = [
        node
        for node in tree.body
        if _assignment_name(node) in assignments
        or (
            isinstance(node, ast.ClassDef)
            and node.name == class_name
        )
    ]
    if (
        len(
            [
                node
                for node in body
                if isinstance(node, ast.ClassDef)
            ]
        )
        != 1
        or {
            name
            for node in body
            if (name := _assignment_name(node)) is not None
        }
        != assignments
    ):
        raise ParityError(f"frozen weighted entrypoint changed: {method_id}")
    namespace: dict[str, object] = {"Counter": Counter}
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=body, type_ignores=[])
            ),
            filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            mode="exec",
        ),
        namespace,
    )
    cls = cast(type[object], namespace[class_name])
    instance = cls.__new__(cls)
    cast(Any, instance).engine = _FrozenEngineReference()
    selector = selector_class.__new__(selector_class)
    cast(Any, selector).rules = {"maxNumber": 49}
    cast(Any, instance).selector = selector
    return getattr(instance, method_name)


class _FakeDatabase:
    def __init__(self, history: list[dict[str, object]]) -> None:
        self._history = history

    def get_all_draws(self, *, lottery_type: str) -> list[dict[str, object]]:
        if lottery_type != "BIG_LOTTO":
            raise ParityError("frozen Elite-7 lottery type changed")
        return self._history


class _DatabaseFactory:
    def __init__(self, history: list[dict[str, object]]) -> None:
        self._history = history

    def __call__(self, **_kwargs: object) -> _FakeDatabase:
        return _FakeDatabase(self._history)


class _JsonCapture:
    def __init__(self, box: dict[str, object]) -> None:
        self._box = box

    def dump(self, value: object, *_args: object, **_kwargs: object) -> None:
        self._box["output"] = value


class _EliteEntrypoint:
    def __init__(
        self,
        function: object,
        namespace: dict[str, object],
        capture: dict[str, object],
    ) -> None:
        self._function = function
        self._namespace = namespace
        self._capture = capture

    def __call__(
        self,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        self._capture.clear()
        self._namespace["DatabaseManager"] = _DatabaseFactory(history)
        with contextlib.redirect_stdout(io.StringIO()):
            cast(Any, self._function)()
        output = self._capture.get("output")
        if not isinstance(output, dict):
            raise ParityError("frozen Elite-7 output was not captured")
        return cast(dict[str, object], output)


def _get_rules(_lottery_type: object) -> dict[str, int]:
    return {"maxNumber": 49, "minNumber": 1, "pickCount": 6}


def _open_capture(*_args: object, **_kwargs: object) -> io.StringIO:
    return io.StringIO()


def _compile_elite_entrypoint(source_text: str) -> _EliteEntrypoint:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{ELITE_SEVEN_METHOD_ID}",
    )
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "predict_7bet_optimized"
    ]
    if len(matches) != 1:
        raise ParityError("frozen Elite-7 entrypoint changed")
    capture: dict[str, object] = {}
    namespace: dict[str, object] = {
        "Counter": Counter,
        "UnifiedPredictionEngine": _FrozenEngineReference,
        "datetime": datetime,
        "get_lottery_rules": _get_rules,
        "json": _JsonCapture(capture),
        "open": _open_capture,
        "os": os,
        "project_root": "/frozen",
        "sys": sys,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=cast(list[ast.stmt], matches),
                    type_ignores=[],
                )
            ),
            filename=f"{FROZEN_SOURCE_COMMIT}:{ELITE_SEVEN_METHOD_ID}",
            mode="exec",
        ),
        namespace,
    )
    return _EliteEntrypoint(
        namespace["predict_7bet_optimized"],
        namespace,
        capture,
    )


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "date": f"FROZEN-{draw.draw_number}",
            "draw": draw.draw_number,
            "draw_number": draw.draw_number,
            "numbers": draw.numbers,
        }
        for draw in reversed(history)
    ]


def _source_result(
    *,
    method_id: str,
    entrypoint: object,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[
    tuple[tuple[int, ...], ...],
    tuple[int, ...],
    tuple[int, ...],
]:
    source_history = _source_history(history)
    rules = {"minNumber": 1, "maxNumber": 49, "pickCount": 6}
    with contextlib.redirect_stdout(io.StringIO()):
        result = (
            cast(Any, entrypoint)(source_history, rules)
            if method_id in _CLASS_ENTRYPOINTS
            else cast(Any, entrypoint)(source_history)
        )
    if not isinstance(result, dict):
        raise ParityError(f"frozen source result changed: {method_id}")
    bets = cast(list[dict[str, object]], result["bets"])
    tickets = tuple(
        tuple(cast(list[int], row["numbers"])) for row in bets
    )
    candidates = (
        tuple(cast(list[int], result["candidates"]))
        if method_id in _CLASS_ENTRYPOINTS
        else ()
    )
    kill_numbers = (
        tuple(cast(list[int], result["kill_numbers"]))
        if method_id in _CLASS_ENTRYPOINTS
        else ()
    )
    return tickets, candidates, kill_numbers


def verify_wave28_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute frozen high-level AST entrypoints and compare port rows."""

    source_by_method: dict[str, bytes] = {}
    source_artifacts: list[dict[str, str]] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
        source = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        digest = hashlib.sha256(source).hexdigest()
        if (
            digest
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE28_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        source_by_method[method_id] = source
        source_artifacts.append({"path": method_id, "sha256": digest})

    support_by_path = {
        path: expected_sha256
        for artifacts in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE28_METHOD.values()
        )
        for path, expected_sha256 in artifacts
    }
    support_artifacts: list[dict[str, str]] = []
    support_source: dict[str, bytes] = {}
    for path, expected_sha256 in sorted(support_by_path.items()):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ParityError(f"frozen support SHA changed: {path}")
        support_source[path] = raw
        support_artifacts.append({"path": path, "sha256": digest})

    selector_class = _compile_negative_selector(
        support_source[_NEGATIVE_SELECTOR_PATH].decode("utf-8")
    )
    entrypoints = {
        method_id: (
            _compile_elite_entrypoint(
                source_by_method[method_id].decode("utf-8")
            )
            if method_id == ELITE_SEVEN_METHOD_ID
            else _compile_weighted_entrypoint(
                source_by_method[method_id].decode("utf-8"),
                method_id=method_id,
                selector_class=selector_class,
            )
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS
    }

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
    closed_count = 0
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target_draw_number = (
            pinned.draws[history_count].draw_number
            if history_count < len(pinned.draws)
            else f"AFTER_{history[-1].draw_number}"
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE28_METHODS:
            source_error: Exception | None = None
            reference: tuple[
                tuple[tuple[int, ...], ...],
                tuple[int, ...],
                tuple[int, ...],
            ] | None = None
            try:
                reference = _source_result(
                    method_id=method_id,
                    entrypoint=entrypoints[method_id],
                    history=history,
                )
            except Exception as exc:
                source_error = exc
            try:
                port = generate_legacy_source_native_wave28_portfolio(
                    LegacySourceNativeWave28Request(
                        legacy_method_id=method_id,
                        target_draw_number=target_draw_number,
                        history=history,
                    )
                )
            except LegacySourceNativeWave28SourceError as exc:
                if source_error is None:
                    raise ParityError(
                        f"port closed but source executed: "
                        f"{method_id}:{history_count}"
                    ) from exc
                closed_count += 1
                cases.append(
                    {
                        "history_draw_count": history_count,
                        "legacy_method_id": method_id,
                        "reason_code": exc.reason_code,
                        "status": "CLOSED_PARITY",
                    }
                )
                continue
            if source_error is not None or reference is None:
                raise ParityError(
                    f"source closed but port executed: "
                    f"{method_id}:{history_count}"
                ) from source_error
            reference_tickets, reference_candidates, reference_kill = (
                reference
            )
            if (
                port.tickets != reference_tickets
                or port.metadata.candidate_pool != reference_candidates
                or port.metadata.kill_numbers != reference_kill
            ):
                raise ParityError(
                    f"output differs: {method_id}:{history_count}"
                )
            cases.append(
                {
                    "candidate_k": port.metadata.candidate_pool_size,
                    "history_draw_count": history_count,
                    "kill_numbers": list(port.metadata.kill_numbers),
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
        "closed_parity_case_count": closed_count,
        "database_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_native_protocol": SOURCE_NATIVE_WAVE28_PROTOCOL,
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
    result = verify_wave28_parity(
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
