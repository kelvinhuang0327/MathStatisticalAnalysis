#!/usr/bin/env python3
"""Verify wave-27 ports against the frozen weighted-portfolio AST sources."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave27 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD,
    GEMINI_2BET_METHOD_ID,
    GEMINI_3BET_METHOD_ID,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD,
    MODEL_V1_METHOD_ID,
    MODEL_V2_METHOD_ID,
    SOURCE_NATIVE_WAVE27_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS,
    LegacySourceNativeWave27Request,
    LegacySourceNativeWave27SourceError,
    frozen_wave27_engine_output,
    generate_legacy_source_native_wave27_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE27_PARITY_V1"
)
_CANDIDATE_CLOSED_HISTORY_COUNTS = (
    63,
    94,
    105,
    202,
    207,
    240,
    261,
    375,
    406,
    1338,
    2114,
)
_HISTORY_COUNTS = (
    *range(1, 61),
    *_CANDIDATE_CLOSED_HISTORY_COUNTS,
    150,
    2148,
)
_CLASS_ENTRYPOINTS = {
    MODEL_V1_METHOD_ID: ("BigLotto2BetOptimizer", "predict_2bets"),
    MODEL_V2_METHOD_ID: (
        "BigLotto2BetOptimizerV2",
        "predict_2bets_optimized",
    ),
}
_FUNCTION_ENTRYPOINTS = {
    GEMINI_2BET_METHOD_ID: "generate_2bet_v1",
    GEMINI_3BET_METHOD_ID: "generate_3bet_diversified",
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


def _source_node(
    source_text: str,
    *,
    method_id: str,
) -> ast.ClassDef | ast.FunctionDef:
    tree = ast.parse(
        source_text,
        filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
    )
    if method_id in _CLASS_ENTRYPOINTS:
        expected_name = _CLASS_ENTRYPOINTS[method_id][0]
        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == expected_name
        ]
    else:
        expected_name = _FUNCTION_ENTRYPOINTS[method_id]
        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == expected_name
        ]
    if len(matches) != 1:
        raise ParityError(f"frozen entrypoint changed: {method_id}")
    return matches[0]


def _compile_entrypoint(
    source_text: str,
    *,
    method_id: str,
) -> object:
    node = _source_node(source_text, method_id=method_id)
    module = ast.fix_missing_locations(
        ast.Module(body=[node], type_ignores=[])
    )
    namespace: dict[str, object] = {"Counter": Counter}
    exec(
        compile(
            module,
            filename=f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            mode="exec",
        ),
        namespace,
    )
    if method_id in _CLASS_ENTRYPOINTS:
        class_name, method_name = _CLASS_ENTRYPOINTS[method_id]
        cls = cast(type[object], namespace[class_name])
        instance = cls.__new__(cls)
        cast(Any, instance).engine = _FrozenEngineReference()
        return getattr(instance, method_name)
    return namespace[_FUNCTION_ENTRYPOINTS[method_id]]


def _to_history(
    history: list[dict[str, object]],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=cast(str, row["draw_number"]),
            numbers=cast(tuple[int, int, int, int, int, int], row["numbers"]),
        )
        for row in history
    )


class _FrozenEngineReference:
    @staticmethod
    def _result(
        method_name: str,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "numbers": list(
                frozen_wave27_engine_output(
                    method_name,
                    _to_history(history),
                )
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

    def bayesian_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("bayesian", history)

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._result("frequency", history)


def _source_result(
    *,
    method_id: str,
    entrypoint: object,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]] | None:
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
    if len(history) < minimum:
        return None
    source_history = [
        {
            "draw_number": draw.draw_number,
            "numbers": draw.numbers,
        }
        for draw in history
    ]
    rules = {"minNumber": 1, "maxNumber": 49, "pickCount": 6}
    callable_entrypoint = cast(Any, entrypoint)
    with contextlib.redirect_stdout(io.StringIO()):
        result = (
            callable_entrypoint(source_history, rules)
            if method_id in _CLASS_ENTRYPOINTS
            else callable_entrypoint(
                _FrozenEngineReference(),
                source_history,
                rules,
            )
        )
    if result is None:
        return None
    if method_id in _CLASS_ENTRYPOINTS:
        payload = cast(dict[str, Any], result)
        rows = [
            cast(list[int], cast(dict[str, Any], row)["numbers"])
            for row in cast(list[object], payload["bets"])
        ]
        candidates = cast(list[int], payload["candidates"])
    else:
        rows = cast(list[list[int]], result)
        specifications = (
            (
                ("deviation", 1.5),
                ("markov", 1.5),
                ("statistical", 1.2),
                ("bayesian", 1.0),
                ("frequency", 1.0),
            )
            if method_id == MODEL_V2_METHOD_ID
            else (
                ("deviation", 2.0),
                ("markov", 1.5),
                ("statistical", 1.0),
            )
        )
        limit = 18 if method_id == GEMINI_3BET_METHOD_ID else 12
        scores: Counter[int] = Counter()
        for method_name, weight in specifications:
            for number in frozen_wave27_engine_output(
                method_name,
                history,
            ):
                scores[number] += cast(int, weight)
        candidates = [
            number for number, _score in scores.most_common(limit)
        ]
    return (
        tuple(tuple(row) for row in rows),
        tuple(candidates),
    )


def verify_wave27_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute frozen high-level AST entrypoints and compare every port row."""

    source_artifacts: list[dict[str, str]] = []
    entrypoints: dict[str, object] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
        source = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        digest = hashlib.sha256(source).hexdigest()
        if (
            digest
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE27_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        entrypoints[method_id] = _compile_entrypoint(
            source.decode("utf-8"),
            method_id=method_id,
        )
        source_artifacts.append(
            {
                "path": method_id,
                "sha256": digest,
            }
        )
    support_by_path = {
        path: expected_sha256
        for artifacts in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE27_METHOD.values()
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
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE27_METHODS:
            reference = _source_result(
                method_id=method_id,
                entrypoint=entrypoints[method_id],
                history=history,
            )
            try:
                port = generate_legacy_source_native_wave27_portfolio(
                    LegacySourceNativeWave27Request(
                        legacy_method_id=method_id,
                        target_draw_number=target_draw_number,
                        history=history,
                    )
                )
            except LegacySourceNativeWave27SourceError as exc:
                expected_reason = (
                    "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
                    if history_count
                    < MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE27_METHOD[
                        method_id
                    ]
                    else (
                        "FROZEN_SOURCE_CANDIDATE_POOL_BELOW_REQUIRED_SLICE"
                    )
                )
                if (
                    reference is not None
                    or exc.reason_code != expected_reason
                ):
                    raise ParityError(
                        f"closed parity differs: {method_id}:{history_count}"
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
            if reference is None:
                raise ParityError(
                    f"source closed but port executed: {method_id}:{history_count}"
                )
            reference_tickets, reference_candidates = reference
            if (
                port.tickets != reference_tickets
                or port.metadata.candidate_pool != reference_candidates
            ):
                raise ParityError(
                    f"output differs: {method_id}:{history_count}"
                )
            cases.append(
                {
                    "candidate_k": port.metadata.candidate_pool_size,
                    "history_draw_count": history_count,
                    "legacy_method_id": method_id,
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
        "source_native_protocol": SOURCE_NATIVE_WAVE27_PROTOCOL,
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
    result = verify_wave27_parity(
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
