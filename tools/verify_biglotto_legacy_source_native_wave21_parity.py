#!/usr/bin/env python3
"""Verify wave-21 port against the frozen post-selection implementation."""

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
from lottolab.application.legacy_source_native_portfolios_wave21 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD,
    POST_SELECTION_FILTER_METHOD_ID,
    SOURCE_NATIVE_WAVE21_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD,
    LegacySourceNativeWave21Request,
    generate_legacy_source_native_wave21_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)
from verify_biglotto_legacy_source_native_wave20_parity import (
    load_frozen_zone_balance_engine,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE21_PARITY_V1"
)
_HISTORY_COUNTS = (1, 3, 50, 500, 2148)
_SUPPORT_PATH = "lottery_api/models/unified_predictor.py"


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


def _assigned_name(node: ast.stmt) -> str | None:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    return target.id if isinstance(target, ast.Name) else None


def _load_frozen_post_selection(
    source_text: str,
    source_identity: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "PostSelectionBacktester"
    ]
    if len(classes) != 1:
        raise ParityError("frozen post-selection class is missing")
    methods = {
        node.name: node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef)
    }
    danger_method = methods.get("_get_danger_numbers")
    run_method = methods.get("run")
    if danger_method is None or run_method is None:
        raise ParityError("frozen post-selection methods are missing")
    loops = [
        node
        for node in ast.walk(run_method)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Tuple)
        and any(
            isinstance(item, ast.Name) and item.id == "target_draw"
            for item in node.target.elts
        )
    ]
    if len(loops) != 1:
        raise ParityError("frozen source backtest loop changed")
    loop_body = loops[0].body
    start = next(
        (
            index
            for index, node in enumerate(loop_body)
            if _assigned_name(node) == "danger_nums"
        ),
        None,
    )
    end = next(
        (
            index
            for index, node in enumerate(loop_body)
            if _assigned_name(node) == "actual"
        ),
        None,
    )
    if start is None or end is None or start >= end:
        raise ParityError("frozen ticket-selection statements changed")
    selection_body = loop_body[start:end]
    required_assignments = {
        "danger_nums",
        "history_50",
        "all_nums_50",
        "freq_50",
        "bet1",
        "candidates",
        "ptr",
        "bet2",
    }
    assigned = {
        name
        for node in selection_body
        for name in (_assigned_name(node),)
        if name is not None
    }
    if not required_assignments.issubset(assigned):
        raise ParityError("frozen ticket-selection assignments changed")
    predictor = ast.FunctionDef(
        name="predict_tickets",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self"),
                ast.arg(arg="history"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[
                    ast.Name(id="swaps_total", ctx=ast.Store()),
                ],
                value=ast.Constant(value=0),
            ),
            *selection_body,
            ast.Return(
                value=ast.List(
                    elts=[
                        ast.Name(id="bet1", ctx=ast.Load()),
                        ast.Name(id="bet2", ctx=ast.Load()),
                    ],
                    ctx=ast.Load(),
                )
            ),
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
        type_params=[],
    )
    selected_class = ast.ClassDef(
        name="_FrozenPostSelection",
        bases=[],
        keywords=[],
        body=[danger_method, predictor],
        decorator_list=[],
        type_params=[],
    )
    module = ast.Module(body=[selected_class], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["_FrozenPostSelection"]


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


def _compare_case(
    *,
    source_class: type[Any],
    engine_class: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
    target_draw_number: str,
) -> dict[str, object]:
    source = source_class()
    source.engine = engine_class()
    source.rules = {
        "minNumber": 1,
        "maxNumber": 49,
        "pickCount": 6,
    }
    source_tickets = [
        sorted(ticket)
        for ticket in source.predict_tickets(_source_history(history))
    ]
    port = generate_legacy_source_native_wave21_portfolio(
        LegacySourceNativeWave21Request(
            legacy_method_id=POST_SELECTION_FILTER_METHOD_ID,
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
        "danger_numbers": list(port.metadata.danger_numbers),
        "history_draw_count": len(history),
        "legacy_method_id": POST_SELECTION_FILTER_METHOD_ID,
        "native_duplicate_ticket_count": (
            port.metadata.native_duplicate_ticket_count
        ),
        "native_ticket_count": len(port_tickets),
        "ticket_sha256": hashlib.sha256(
            _canonical_bytes(port_tickets)
        ).hexdigest(),
        "zone_retry_used": port.metadata.zone_retry_used,
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
    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{POST_SELECTION_FILTER_METHOD_ID}",
    )
    expected_source_sha = (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE21_METHOD[
            POST_SELECTION_FILTER_METHOD_ID
        ]
    )
    if hashlib.sha256(source_raw).hexdigest() != expected_source_sha:
        raise ParityError("frozen source SHA changed")
    source_class = _load_frozen_post_selection(
        source_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{POST_SELECTION_FILTER_METHOD_ID}",
    )

    support_expected = (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE21_METHOD[
            POST_SELECTION_FILTER_METHOD_ID
        ][0][1]
    )
    support_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )
    if hashlib.sha256(support_raw).hexdigest() != support_expected:
        raise ParityError("frozen support source SHA changed")
    engine_class = load_frozen_zone_balance_engine(
        support_raw.decode("utf-8"),
        f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
    )

    cases = [
        _compare_case(
            source_class=source_class,
            engine_class=engine_class,
            history=all_history[:count],
            target_draw_number=f"parity-after-{count}",
        )
        for count in _HISTORY_COUNTS
    ]
    danger_history = (
        LegacyHistoryDraw("danger-1", (1, 2, 3, 4, 5, 6)),
        LegacyHistoryDraw("danger-2", (1, 7, 8, 9, 10, 11)),
        LegacyHistoryDraw("danger-3", (1, 12, 13, 14, 15, 16)),
    )
    cases.append(
        _compare_case(
            source_class=source_class,
            engine_class=engine_class,
            history=danger_history,
            target_draw_number="parity-danger-retry",
        )
    )
    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "execution_mode": (
            "AST_COMPILE_FROZEN_POST_SELECTION_STATEMENTS_AND_"
            "UNIFIED_ZONE_BALANCE_METHODS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE21_PROTOCOL,
        "source_artifact": {
            "path": POST_SELECTION_FILTER_METHOD_ID,
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    (
                        f"{FROZEN_SOURCE_COMMIT}:"
                        f"{POST_SELECTION_FILTER_METHOD_ID}"
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
            "source_blob_id": (
                _git(
                    frozen_root,
                    "rev-parse",
                    f"{FROZEN_SOURCE_COMMIT}:{_SUPPORT_PATH}",
                )
                .decode("ascii")
                .strip()
            ),
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
