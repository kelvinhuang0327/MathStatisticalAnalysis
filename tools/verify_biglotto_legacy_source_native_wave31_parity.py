#!/usr/bin/env python3
"""Verify wave-31 ports against the frozen radical class-method ASTs."""

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

from lottolab.application.legacy_frozen_unified_core import (
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD,
    RADICAL_BACKTEST_METHOD_ID,
    RADICAL_PREDICT_METHOD_ID,
    SOURCE_NATIVE_WAVE31_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS,
    LegacySourceNativeWave31Request,
    LegacySourceNativeWave31SourceError,
    generate_legacy_source_native_wave31_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE31_PARITY_V1"
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


class _FrozenEngineReference:
    @staticmethod
    def _history(
        history: list[dict[str, object]],
    ) -> tuple[LegacyHistoryDraw, ...]:
        return tuple(
            LegacyHistoryDraw(
                draw_number=cast(str, row["draw_number"]),
                numbers=cast(
                    tuple[int, int, int, int, int, int],
                    row["numbers"],
                ),
            )
            for row in history
        )

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {
            "numbers": list(frozen_deviation_ticket(self._history(history)))
        }

    def markov_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {
            "numbers": list(frozen_markov_ticket(self._history(history))[0])
        }

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {
            "numbers": list(frozen_frequency_ticket(self._history(history)))
        }


def _class_method(
    source_text: str,
    *,
    class_name: str,
    method_name: str,
) -> tuple[type[Any], ast.FunctionDef]:
    tree = ast.parse(source_text)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(classes) != 1:
        raise ParityError("frozen radical class changed")
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    ]
    if len(methods) != 1:
        raise ParityError("frozen radical method changed")
    namespace: dict[str, object] = {
        "Counter": Counter,
        "UnifiedPredictionEngine": _FrozenEngineReference,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[classes[0]], type_ignores=[])
            ),
            filename=f"{class_name}.{method_name}",
            mode="exec",
        ),
        namespace,
    )
    class_object = cast(type[Any], namespace[class_name])
    return class_object, methods[0]


def _history_dicts(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw": draw.draw_number,
            "draw_number": draw.draw_number,
            "numbers": draw.numbers,
        }
        for draw in history
    ]


def _reference_predict(
    class_object: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    instance = object.__new__(class_object)
    instance.engine = _FrozenEngineReference()
    filtered = tuple(
        draw for draw in reversed(history) if draw.draw_number != "115000007"
    )
    with contextlib.redirect_stdout(io.StringIO()):
        result = cast(
            dict[str, object],
            instance.predict_gap_strategy(
                _history_dicts(filtered),
                {"minNumber": 1, "maxNumber": 49, "pickCount": 6},
                gap_zone=1,
            ),
        )
    return (
        tuple(cast(list[int], result["numbers"])),
        tuple(cast(list[int], result["candidates"])),
    )


def _reference_backtest(
    class_object: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], ...]:
    instance = object.__new__(class_object)
    instance.engine = _FrozenEngineReference()
    newest_300 = tuple(reversed(history))[:300]
    rows = (
        instance._predict_gap(
            _history_dicts(newest_300),
            range(1, 20),
        ),
        instance._predict_gap(
            _history_dicts(newest_300),
            range(20, 30),
        ),
    )
    return tuple(tuple(cast(list[int], row)) for row in rows)


def _behavior_facts(
    method_id: str,
    source_text: str,
    method_node: ast.FunctionDef,
) -> dict[str, object]:
    constants = {
        node.value
        for node in ast.walk(ast.parse(source_text))
        if isinstance(node, ast.Constant)
    }
    method_constants = {
        node.value
        for node in ast.walk(method_node)
        if isinstance(node, ast.Constant)
    }
    if method_id == RADICAL_PREDICT_METHOD_ID:
        if (
            "115000007" not in constants
            or 150 not in method_constants
            or 12 not in method_constants
        ):
            raise ParityError("frozen live radical constants changed")
        return {
            "candidate_pool_limit": 12,
            "hardcoded_history_exclusion_draw": "115000007",
            "low_sum_shift_threshold": 150,
            "main_gap_zone": 1,
        }
    if 12 not in method_constants:
        raise ParityError("frozen radical backtest constants changed")
    if "window=300" not in source_text or "if i < 50" not in source_text:
        raise ParityError("frozen radical rolling wrapper changed")
    return {
        "candidate_pool_limit": 12,
        "gap_ranges": [[1, 19], [20, 29]],
        "source_history_limit": 300,
        "warmup_draw_count": 50,
    }


def verify_wave31_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute frozen class methods and compare causal port rows."""

    sources: dict[str, str] = {}
    classes: dict[str, type[Any]] = {}
    behavior: dict[str, dict[str, object]] = {}
    source_artifacts: list[dict[str, str]] = []
    for method_id, class_name, method_name in (
        (
            RADICAL_PREDICT_METHOD_ID,
            "RadicalPredictor",
            "predict_gap_strategy",
        ),
        (
            RADICAL_BACKTEST_METHOD_ID,
            "RadicalBacktester",
            "_predict_gap",
        ),
    ):
        raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE31_METHOD[
            method_id
        ]:
            raise ParityError("frozen radical source SHA changed")
        source_text = raw.decode("utf-8")
        class_object, method_node = _class_method(
            source_text,
            class_name=class_name,
            method_name=method_name,
        )
        sources[method_id] = source_text
        classes[method_id] = class_object
        behavior[method_id] = _behavior_facts(
            method_id,
            source_text,
            method_node,
        )
        source_artifacts.append({"path": method_id, "sha256": digest})

    support_artifacts: list[dict[str, str]] = []
    for path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE31_METHOD[
            RADICAL_PREDICT_METHOD_ID
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
    closed_case_count = 0
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target = (
            pinned.draws[history_count].draw_number
            if history_count < len(pinned.draws)
            else f"AFTER_{history[-1].draw_number}"
        )
        for method_id in SUPPORTED_SOURCE_NATIVE_WAVE31_METHODS:
            if (
                method_id == RADICAL_BACKTEST_METHOD_ID
                and history_count < 50
            ):
                closed_case_count += 1
                cases.append(
                    {
                        "history_draw_count": history_count,
                        "legacy_method_id": method_id,
                        "reason_code": (
                            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
                        ),
                        "status": "CLOSED_INSUFFICIENT_HISTORY",
                    }
                )
                continue
            if method_id == RADICAL_PREDICT_METHOD_ID:
                reference_ticket, reference_pool = _reference_predict(
                    classes[method_id],
                    history,
                )
                reference = (reference_ticket,)
            else:
                reference = _reference_backtest(
                    classes[method_id],
                    history,
                )
                reference_pool = ()
            if any(
                len(ticket) != 6 or len(set(ticket)) != 6
                for ticket in reference
            ):
                try:
                    generate_legacy_source_native_wave31_portfolio(
                        LegacySourceNativeWave31Request(
                            legacy_method_id=method_id,
                            target_draw_number=target,
                            history=history,
                        )
                    )
                except LegacySourceNativeWave31SourceError as exc:
                    if (
                        exc.reason_code
                        != "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
                    ):
                        raise ParityError(
                            "invalid-output reason differs"
                        ) from exc
                else:
                    raise ParityError("invalid source output was accepted")
                closed_case_count += 1
                cases.append(
                    {
                        "history_draw_count": history_count,
                        "legacy_method_id": method_id,
                        "reason_code": (
                            "FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET"
                        ),
                        "status": "CLOSED_INVALID_OUTPUT",
                    }
                )
                continue
            port = generate_legacy_source_native_wave31_portfolio(
                LegacySourceNativeWave31Request(
                    legacy_method_id=method_id,
                    target_draw_number=target,
                    history=history,
                )
            )
            if (
                method_id == RADICAL_PREDICT_METHOD_ID
                and port.metadata.candidate_pools != (reference_pool,)
            ):
                raise ParityError(
                    f"candidate pool differs: {history_count}"
                )
            if port.tickets != reference:
                raise ParityError(
                    f"ticket output differs: {method_id}:{history_count}"
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
        "closed_parity_case_count": closed_case_count,
        "database_sha256": pinned.database_sha256_before,
        "frozen_source_behavior_facts": behavior,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_instrumentation": (
            "FROZEN_CLASS_METHOD_AST_EXECUTION_WITH_VALIDATED_MAIN_WRAPPER_"
            "CONSTANTS_AND_FROZEN_UNIFIED_ENGINE_REFERENCE"
        ),
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": source_artifacts,
        "source_native_protocol": SOURCE_NATIVE_WAVE31_PROTOCOL,
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
    result = verify_wave31_parity(
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
