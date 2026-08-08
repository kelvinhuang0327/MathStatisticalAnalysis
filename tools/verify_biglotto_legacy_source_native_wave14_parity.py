#!/usr/bin/env python3
"""Verify wave-14 ports against classes compiled from frozen source text."""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave14 import (
    GRAPH_PREDICTOR_METHOD_ID,
    HIGH_PRIZE_TREND_METHOD_ID,
    SOURCE_NATIVE_WAVE14_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD,
    LegacySourceNativeWave14Request,
    generate_legacy_source_native_wave14_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE14_PARITY_V1"
)
_HISTORY_COUNTS = (100, 300, 2148)
_TREND_LAMBDAS = (0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15)
_CLASS_BY_METHOD = {
    GRAPH_PREDICTOR_METHOD_ID: "CooccurrenceGraphPredictor",
    HIGH_PRIZE_TREND_METHOD_ID: "HighPrizeTrendOptimizer",
}


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _ScalarNumpyCompatibility:
    @staticmethod
    def exp(value: float) -> float:
        return math.exp(value)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _frozen_source(
    frozen_root: Path,
    method_id: str,
) -> tuple[str, bytes]:
    completed = subprocess.run(
        (
            "git",
            "-C",
            str(frozen_root),
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
        ),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityError("cannot read frozen source blob")
    raw = completed.stdout
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParityError("frozen source is not UTF-8") from exc
    return text, raw


def _load_class(
    source_text: str,
    source_identity: str,
    class_name: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(selected) != 1:
        raise ParityError(f"frozen class missing: {class_name}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "__builtins__": __builtins__,
        "defaultdict": defaultdict,
        "itertools": itertools,
        "np": _ScalarNumpyCompatibility,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace[class_name]


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw_number": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in history
    ]


def _source_tickets(
    method_id: str,
    source_class: type[Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    rules = {
        "maxNumber": 49,
        "minNumber": 1,
        "pickCount": 6,
    }
    if method_id == GRAPH_PREDICTOR_METHOD_ID:
        result = source_class().predict(history, rules)
        return [sorted(result["numbers"])]
    if method_id == HIGH_PRIZE_TREND_METHOD_ID:
        return [
            sorted(
                source_class(lambda_value).predict(history, rules)[
                    "numbers"
                ]
            )
            for lambda_value in _TREND_LAMBDAS
        ]
    raise ParityError("method is outside wave 14")


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
    source_classes: dict[str, type[Any]] = {}
    for method_id, class_name in _CLASS_BY_METHOD.items():
        source_text, source_raw = _frozen_source(
            frozen_root,
            method_id,
        )
        if hashlib.sha256(source_raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[method_id]
        ):
            raise ParityError("frozen source SHA changed")
        source_classes[method_id] = _load_class(
            source_text,
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            class_name,
        )

    cases: list[dict[str, object]] = []
    for count in _HISTORY_COUNTS:
        history = all_history[:count]
        source_history = _source_history(history)
        for method_id in _CLASS_BY_METHOD:
            frozen_tickets = _source_tickets(
                method_id,
                source_classes[method_id],
                source_history,
            )
            port = generate_legacy_source_native_wave14_portfolio(
                LegacySourceNativeWave14Request(
                    legacy_method_id=method_id,
                    target_draw_number=f"parity-after-{count}",
                    history=history,
                )
            )
            port_tickets = [list(ticket) for ticket in port.tickets]
            if frozen_tickets != port_tickets:
                raise ParityError(
                    f"ticket parity failed for {method_id} at {count}"
                )
            cases.append(
                {
                    "history_draw_count": count,
                    "legacy_method_id": method_id,
                    "native_duplicate_ticket_count": (
                        port.metadata.native_duplicate_ticket_count
                    ),
                    "native_ticket_count": len(port.tickets),
                    "ticket_sha256": hashlib.sha256(
                        _canonical_bytes(port_tickets)
                    ).hexdigest(),
                }
            )
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_CLASSES_WITH_SCALAR_NUMPY_EXP_"
            "COMPATIBILITY_AND_COMPARE_ORDERED_NATIVE_TICKETS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE14_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD
        ),
        "status": "PASS",
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
                "sha256": hashlib.sha256(payload).hexdigest(),
                "status": "PASS",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
