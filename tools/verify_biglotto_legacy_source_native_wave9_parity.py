#!/usr/bin/env python3
"""Verify wave-9 ports against functions compiled from frozen source text."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave9 import (
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
    P0P1_UPGRADE_METHOD_ID,
    SOURCE_NATIVE_WAVE9_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD,
    TRUE_ORTHOGONAL_METHOD_ID,
    LegacySourceNativeWave9Request,
    generate_legacy_source_native_wave9_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE9_PARITY_V1"
)
_FUNCTION_NAMES = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: {
        "build_cooccurrence_matrix",
        "find_cluster_centers",
        "expand_from_anchor",
        "cluster_pivot_single_bet",
        "cluster_pivot_2bet",
        "cluster_pivot_3bet",
        "cluster_pivot_4bet",
        "cluster_pivot_windowed",
        "cluster_pivot_hybrid",
    },
    TRUE_ORTHOGONAL_METHOD_ID: {
        "cluster_pivot_predict",
        "pure_frequency_predict",
        "pure_gap_predict",
        "zone_balance_predict",
        "odd_even_balance_predict",
        "true_orthogonal_2bet",
        "true_orthogonal_3bet",
        "true_orthogonal_4bet",
        "cluster_pivot_multi_window",
        "diversity_enforced_4bet",
    },
    P0P1_UPGRADE_METHOD_ID: {
        "deviation_complement_2bet_original",
        "structural_score",
        "mixed_3bet_original",
        "deviation_complement_2bet_p0",
        "mixed_3bet_p0p1",
    },
}
_HISTORY_COUNTS = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: (50, 100, 2148),
    TRUE_ORTHOGONAL_METHOD_ID: (100, 300, 2148),
    P0P1_UPGRADE_METHOD_ID: (1, 100, 2148),
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


def _load_functions(
    source_text: str,
    source_identity: str,
    names: set[str],
) -> dict[str, Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    found_names = {
        node.name
        for node in selected
        if isinstance(node, ast.FunctionDef)
    }
    if found_names != names:
        missing = sorted(names - found_names)
        raise ParityError(
            f"frozen functions missing from {source_identity}: {missing}"
        )
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "defaultdict": defaultdict,
        "combinations": combinations,
        "Dict": dict,
        "List": list,
        "MAX_NUM": 49,
        "PICK": 6,
        "Set": set,
        "Tuple": tuple,
        "random": random,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace


def _frozen_source(frozen_root: Path, method_id: str) -> tuple[str, bytes]:
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
        raise ParityError(
            f"cannot read frozen source blob: {method_id}"
        )
    raw = completed.stdout
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParityError(
            f"frozen source is not UTF-8: {method_id}"
        ) from exc
    return text, raw


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {"draw": draw.draw_number, "numbers": list(draw.numbers)}
        for draw in history
    ]


def _source_cluster(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    configurations = (
        [namespace["cluster_pivot_single_bet"](history)],
        namespace["cluster_pivot_2bet"](history),
        namespace["cluster_pivot_3bet"](history),
        namespace["cluster_pivot_4bet"](history),
        namespace["cluster_pivot_windowed"](
            history,
            window=50,
            num_bets=2,
        ),
        namespace["cluster_pivot_hybrid"](history, num_bets=3),
        namespace["cluster_pivot_hybrid"](history, num_bets=4),
    )
    return [
        ticket
        for configuration in configurations
        for ticket in configuration
        if ticket
    ]


def _source_orthogonal(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    configurations = (
        [namespace["cluster_pivot_predict"](history)],
        [namespace["pure_frequency_predict"](history)],
        [namespace["pure_gap_predict"](history)],
        [namespace["zone_balance_predict"](history)],
        namespace["true_orthogonal_2bet"](history),
        namespace["true_orthogonal_3bet"](history),
        namespace["true_orthogonal_4bet"](history),
        namespace["cluster_pivot_multi_window"](history),
        namespace["diversity_enforced_4bet"](history),
    )
    return [
        ticket
        for configuration in configurations
        for ticket in configuration
        if ticket
    ]


def _source_p0p1(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    configurations = (
        namespace["deviation_complement_2bet_original"](history),
        namespace["deviation_complement_2bet_p0"](history),
        namespace["mixed_3bet_original"](history, seed=42),
        namespace["mixed_3bet_p0p1"](history, seed=42),
    )
    return [
        ticket
        for configuration in configurations
        for ticket in configuration
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
        require_replay_authority=False,
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    namespaces: dict[str, dict[str, Any]] = {}
    for method_id, names in _FUNCTION_NAMES.items():
        source_text, source_raw = _frozen_source(
            frozen_root,
            method_id,
        )
        if hashlib.sha256(source_raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        namespaces[method_id] = _load_functions(
            source_text,
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            names,
        )

    cases: list[dict[str, object]] = []
    for method_id, counts in _HISTORY_COUNTS.items():
        for count in counts:
            history = all_history[:count]
            source_history = _source_history(history)
            if method_id == CLUSTER_PIVOT_BENCHMARK_METHOD_ID:
                frozen_tickets = _source_cluster(
                    namespaces[method_id],
                    source_history,
                )
            elif method_id == TRUE_ORTHOGONAL_METHOD_ID:
                frozen_tickets = _source_orthogonal(
                    namespaces[method_id],
                    source_history,
                )
            else:
                frozen_tickets = _source_p0p1(
                    namespaces[method_id],
                    source_history,
                )
            port = generate_legacy_source_native_wave9_portfolio(
                LegacySourceNativeWave9Request(
                    legacy_method_id=method_id,
                    target_draw_number=f"parity-after-{count}",
                    history=history,
                )
            )
            port_tickets = [list(ticket) for ticket in port.tickets]
            if frozen_tickets != port_tickets:
                raise ParityError(
                    f"ticket parity failed: {method_id} at {count}"
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
            "AST_COMPILE_FROZEN_FUNCTIONS_AND_COMPARE_EXACT_TICKET_ORDER"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE9_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD
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
