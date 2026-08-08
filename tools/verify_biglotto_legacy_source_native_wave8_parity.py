#!/usr/bin/env python3
"""Verify wave-8 ports against functions compiled from frozen source text."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from types import MethodType
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave8 import (
    CLUSTER_ENHANCEMENTS_METHOD_ID,
    DYNAMIC_FREQUENCY_METHOD_ID,
    GEMINI_PHASE2_METHOD_ID,
    OPTIMIZE_THIRD_BET_METHOD_ID,
    SOURCE_NATIVE_WAVE8_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD,
    LegacySourceNativeWave8Request,
    generate_legacy_source_native_wave8_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE8_PARITY_V1"
)
_FUNCTION_NAMES = {
    GEMINI_PHASE2_METHOD_ID: {
        "markov_predict",
        "statistical_predict",
        "deviation_predict",
        "frequency_predict",
        "trend_predict",
        "bayesian_predict",
        "hot_cold_mix_predict",
        "generate_7_bets",
    },
    CLUSTER_ENHANCEMENTS_METHOD_ID: {
        "build_cooccurrence_matrix",
        "find_cluster_centers",
        "expand_from_anchor",
        "find_anti_cooccur_numbers",
        "anti_cooccur_predict",
        "build_triplet_matrix",
        "triplet_predict",
        "temporal_cooccur_predict",
        "graph_community_predict",
        "gap_compensation_predict",
        "cluster_pivot_base",
        "orthogonal_4bet",
        "hybrid_5bet",
    },
    OPTIMIZE_THIRD_BET_METHOD_ID: {
        "structural_score",
        "analyze_coverage",
        "generate_optimal_3rd_bet",
    },
}
_HISTORY_COUNTS = {
    GEMINI_PHASE2_METHOD_ID: (100, 300, 2148),
    DYNAMIC_FREQUENCY_METHOD_ID: (200, 350, 2148),
    CLUSTER_ENHANCEMENTS_METHOD_ID: (100, 259, 2131),
    OPTIMIZE_THIRD_BET_METHOD_ID: (1, 100, 2148),
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
        raise ParityError(
            f"frozen functions missing from {source_identity}"
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
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace


def _load_dynamic_class(
    source_text: str,
    source_identity: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "DynamicFrequencyPredictor"
    ]
    if len(selected) != 1:
        raise ParityError("frozen dynamic predictor class missing")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return cast(type[Any], namespace["DynamicFrequencyPredictor"])


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


def _source_gemini(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    rules = {
        "name": "BIG_LOTTO",
        "pickCount": 6,
        "minNumber": 1,
        "maxNumber": 49,
    }
    result = namespace["generate_7_bets"](history, rules)
    return cast(list[list[int]], result)


def _source_dynamic(
    predictor_class: type[Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    instance = object.__new__(predictor_class)
    instance.windows = [30, 50, 100, 200, 300]

    def get_data(_self: object) -> list[dict[str, object]]:
        return history

    instance.get_data = MethodType(get_data, instance)
    result = cast(dict[str, object], instance.predict(pick_count=6))
    return [cast(list[int], result["numbers"])]


def _source_cluster(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    configurations = (
        [namespace["cluster_pivot_base"](history, 49, 6)],
        [namespace["triplet_predict"](history, 49, 6)],
        [namespace["temporal_cooccur_predict"](history, 49, 6)],
        [namespace["gap_compensation_predict"](history, 49, 6)],
        [namespace["graph_community_predict"](history, 49, 6)],
        [namespace["anti_cooccur_predict"](history, 49, 6)],
        namespace["orthogonal_4bet"](history, 49, 6),
        namespace["hybrid_5bet"](history, 49, 6),
    )
    return [
        ticket
        for configuration in configurations
        for ticket in configuration
        if ticket
    ]


def _source_optimize(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    with contextlib.redirect_stdout(io.StringIO()):
        result = namespace["generate_optimal_3rd_bet"](
            [1, 18, 23, 40, 43, 46],
            [16, 21, 22, 31, 40, 48],
            history,
        )
    best_bet = cast(tuple[list[int], object, object], result)[0]
    return [best_bet]


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
            frozen_root, method_id
        )
        if hashlib.sha256(source_raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        namespaces[method_id] = _load_functions(
            source_text,
            f"{FROZEN_SOURCE_COMMIT}:{method_id}",
            names,
        )
    dynamic_text, dynamic_raw = _frozen_source(
        frozen_root, DYNAMIC_FREQUENCY_METHOD_ID
    )
    if hashlib.sha256(dynamic_raw).hexdigest() != (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[
            DYNAMIC_FREQUENCY_METHOD_ID
        ]
    ):
        raise ParityError("frozen dynamic source SHA changed")
    dynamic_class = _load_dynamic_class(
        dynamic_text,
        f"{FROZEN_SOURCE_COMMIT}:{DYNAMIC_FREQUENCY_METHOD_ID}",
    )

    cases: list[dict[str, object]] = []
    for method_id, counts in _HISTORY_COUNTS.items():
        for count in counts:
            history = all_history[:count]
            source_history = _source_history(history)
            if method_id == GEMINI_PHASE2_METHOD_ID:
                frozen_tickets = _source_gemini(
                    namespaces[method_id], source_history
                )
            elif method_id == DYNAMIC_FREQUENCY_METHOD_ID:
                frozen_tickets = _source_dynamic(
                    dynamic_class, source_history
                )
            elif method_id == CLUSTER_ENHANCEMENTS_METHOD_ID:
                frozen_tickets = _source_cluster(
                    namespaces[method_id], source_history
                )
            else:
                frozen_tickets = _source_optimize(
                    namespaces[method_id], source_history
                )
            port = generate_legacy_source_native_wave8_portfolio(
                LegacySourceNativeWave8Request(
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
        "port_protocol": SOURCE_NATIVE_WAVE8_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD
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
