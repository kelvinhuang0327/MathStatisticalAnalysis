#!/usr/bin/env python3
"""Verify wave-20 port against the frozen zone-balance implementation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave20 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD,
    SOURCE_NATIVE_WAVE20_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD,
    ZONE_BALANCE_500_METHOD_ID,
    LegacySourceNativeWave20Request,
    generate_legacy_source_native_wave20_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE20_PARITY_V1"
)
_HISTORY_COUNTS = (1, 100, 500, 2148)
_SUPPORT_PATH = "lottery_api/models/unified_predictor.py"
_METHOD_NAMES = (
    "zone_balance_predict",
    "_dynamic_zone_partition",
    "_calculate_zone_quality",
)
_WINDOWS = (100, 200, 300, 500)


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


def load_frozen_zone_balance_engine(
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
    method_nodes = [
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in _METHOD_NAMES
    ]
    if {method.name for method in method_nodes} != set(_METHOD_NAMES):
        raise ParityError("frozen zone-balance methods are missing")
    methods: list[ast.stmt] = list(method_nodes)
    selected_class = ast.ClassDef(
        name="_FrozenZoneBalanceEngine",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
        type_params=[],
    )
    module = ast.Module(body=[selected_class], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["_FrozenZoneBalanceEngine"]


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in history
    ]


def _source_tickets(
    engine: Any,
    history: tuple[LegacyHistoryDraw, ...],
) -> list[list[int]]:
    rules = {
        "minNumber": 1,
        "maxNumber": 49,
        "pickCount": 6,
    }
    source_history = _source_history(history)
    main = engine.zone_balance_predict(
        source_history[-500:],
        rules,
    )
    comparisons = [
        engine.zone_balance_predict(source_history[-window:], rules)
        for window in _WINDOWS
    ]
    return [
        sorted(result["numbers"])
        for result in (main, *comparisons)
    ]


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
    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{ZONE_BALANCE_500_METHOD_ID}",
    )
    expected_source_sha = (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE20_METHOD[
            ZONE_BALANCE_500_METHOD_ID
        ]
    )
    if hashlib.sha256(source_raw).hexdigest() != expected_source_sha:
        raise ParityError("frozen source SHA changed")
    source_tree = ast.parse(
        source_raw.decode("utf-8"),
        filename=(
            f"{FROZEN_SOURCE_COMMIT}:{ZONE_BALANCE_500_METHOD_ID}"
        ),
    )
    source_constants = {
        value
        for node in ast.walk(source_tree)
        if isinstance(node, ast.Constant)
        and type(node.value) is int
        for value in (node.value,)
    }
    if not {100, 200, 300, 500}.issubset(source_constants):
        raise ParityError("frozen source window declarations changed")

    support_expected = (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE20_METHOD[
            ZONE_BALANCE_500_METHOD_ID
        ][0][1]
    )
    support_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    if hashlib.sha256(support_raw).hexdigest() != support_expected:
        raise ParityError("frozen support source SHA changed")
    support_blob = (
        _git(
            frozen_root,
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
        )
        .decode("ascii")
        .strip()
    )
    frozen_engine_class = load_frozen_zone_balance_engine(
        support_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )

    cases: list[dict[str, object]] = []
    for count in _HISTORY_COUNTS:
        history = all_history[:count]
        source_tickets = _source_tickets(
            frozen_engine_class(),
            history,
        )
        port = generate_legacy_source_native_wave20_portfolio(
            LegacySourceNativeWave20Request(
                legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
                target_draw_number=f"parity-after-{count}",
                history=history,
            )
        )
        port_tickets = [list(ticket) for ticket in port.tickets]
        if source_tickets != port_tickets:
            raise ParityError(f"ticket parity failed at {count}")
        cases.append(
            {
                "history_draw_count": count,
                "legacy_method_id": ZONE_BALANCE_500_METHOD_ID,
                "native_duplicate_ticket_count": (
                    port.metadata.native_duplicate_ticket_count
                ),
                "native_ticket_count": len(port_tickets),
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
            "AST_COMPILE_FROZEN_ZONE_BALANCE_METHODS_AND_COMPARE_"
            "MAIN_500_PLUS_100_200_300_500_POSITIONAL_OUTPUTS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE20_PROTOCOL,
        "source_artifact": {
            "path": ZONE_BALANCE_500_METHOD_ID,
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    (
                        f"{FROZEN_SOURCE_COMMIT}:"
                        f"{ZONE_BALANCE_500_METHOD_ID}"
                    ),
                )
                .decode("ascii")
                .strip()
            ),
            "source_byte_size": len(source_raw),
            "source_sha256": expected_source_sha,
        },
        "status": "PASS",
        "support_artifact": {
            "path": _SUPPORT_PATH,
            "source_blob_id": support_blob,
            "source_byte_size": len(support_raw),
            "source_sha256": support_expected,
        },
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
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
