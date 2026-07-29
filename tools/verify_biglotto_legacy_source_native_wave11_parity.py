#!/usr/bin/env python3
"""Verify wave-11 ports against functions compiled from frozen source text."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave11 import (
    EXHAUSTIVE_NBET_METHOD_ID,
    MUST_HIT_METHOD_ID,
    SOURCE_NATIVE_WAVE11_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD,
    LegacySourceNativeWave11Request,
    generate_legacy_source_native_wave11_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE11_PARITY_V1"
)
_EXHAUSTIVE_FUNCTION_NAMES = {
    "method_frequency_hot",
    "method_frequency_cold",
    "method_gap_pressure",
    "method_markov_transition",
    "method_zone_balance",
    "method_odd_even_balance",
    "method_sum_optimal",
    "method_clustering_centroid",
    "method_entropy_max",
    "method_anti_repeat",
    "method_tail_pattern",
    "method_hybrid_hot_cold",
    "generate_diverse_nbets",
}
_EXHAUSTIVE_METHOD_NAMES = (
    "method_frequency_hot",
    "method_frequency_cold",
    "method_gap_pressure",
    "method_markov_transition",
    "method_zone_balance",
    "method_odd_even_balance",
    "method_sum_optimal",
    "method_clustering_centroid",
    "method_entropy_max",
    "method_anti_repeat",
    "method_tail_pattern",
    "method_hybrid_hot_cold",
)
_HISTORY_COUNTS = {
    EXHAUSTIVE_NBET_METHOD_ID: (500, 1000, 2148),
    MUST_HIT_METHOD_ID: (50, 300, 2148),
}


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


class _NumpyCompat:
    """Minimal exact stand-in for the source's axis-zero binary mean."""

    @staticmethod
    def mean(
        vectors: list[list[int]],
        *,
        axis: int,
    ) -> list[float]:
        if axis != 0 or not vectors:
            raise ParityError("unsupported frozen numpy mean call")
        return [
            sum(row[index] for row in vectors) / len(vectors)
            for index in range(len(vectors[0]))
        ]


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


def _load_exhaustive_functions(
    source_text: str,
    source_identity: str,
) -> dict[str, Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in _EXHAUSTIVE_FUNCTION_NAMES
    ]
    found_names = {
        node.name
        for node in selected
        if isinstance(node, ast.FunctionDef)
    }
    if found_names != _EXHAUSTIVE_FUNCTION_NAMES:
        missing = sorted(_EXHAUSTIVE_FUNCTION_NAMES - found_names)
        raise ParityError(
            f"frozen exhaustive functions missing: {missing}"
        )
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Callable": Any,
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "Tuple": tuple,
        "__builtins__": __builtins__,
        "combinations": combinations,
        "np": _NumpyCompat,
        "random": random,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace


def _load_must_hit_class(
    source_text: str,
    source_identity: str,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "MustHitBacktester"
    ]
    if len(selected) != 1:
        raise ParityError("frozen MustHitBacktester class missing")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace["MustHitBacktester"]


def _source_history(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    newest_first: bool,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"draw": draw.draw_number, "numbers": list(draw.numbers)}
        for draw in history
    ]
    if newest_first:
        rows.reverse()
    return rows


def _source_exhaustive(
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    methods = [
        namespace[name] for name in _EXHAUSTIVE_METHOD_NAMES
    ]
    configurations: list[list[list[int]]] = []
    for number_of_bets in (2, 3):
        for method in methods:
            configurations.append(
                [
                    method(history, 49)
                    for _index in range(number_of_bets)
                ]
            )
        configurations.append(
            namespace["generate_diverse_nbets"](
                history,
                49,
                number_of_bets,
                methods,
            )
        )
    return [
        sorted(ticket)
        for configuration in configurations
        for ticket in configuration
    ]


def _source_must_hit(
    source_class: type[Any],
    history: list[dict[str, object]],
) -> tuple[list[int], ...]:
    instance = object.__new__(source_class)
    return tuple(
        instance.predict_must_hit(history, top_n)
        for top_n in (6, 10, 15)
    )


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
    sources: dict[str, str] = {}
    for method_id in _HISTORY_COUNTS:
        source_text, source_raw = _frozen_source(
            frozen_root,
            method_id,
        )
        if hashlib.sha256(source_raw).hexdigest() != (
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD[method_id]
        ):
            raise ParityError(f"frozen source SHA changed: {method_id}")
        sources[method_id] = source_text
    exhaustive_namespace = _load_exhaustive_functions(
        sources[EXHAUSTIVE_NBET_METHOD_ID],
        f"{FROZEN_SOURCE_COMMIT}:{EXHAUSTIVE_NBET_METHOD_ID}",
    )
    must_hit_class = _load_must_hit_class(
        sources[MUST_HIT_METHOD_ID],
        f"{FROZEN_SOURCE_COMMIT}:{MUST_HIT_METHOD_ID}",
    )

    cases: list[dict[str, object]] = []
    for method_id, counts in _HISTORY_COUNTS.items():
        for count in counts:
            history = all_history[:count]
            port = generate_legacy_source_native_wave11_portfolio(
                LegacySourceNativeWave11Request(
                    legacy_method_id=method_id,
                    target_draw_number=f"parity-after-{count}",
                    history=history,
                )
            )
            port_tickets = [list(ticket) for ticket in port.tickets]
            candidate_pool_sha256: str | None = None
            if method_id == EXHAUSTIVE_NBET_METHOD_ID:
                frozen_tickets = _source_exhaustive(
                    exhaustive_namespace,
                    _source_history(history, newest_first=True),
                )
            else:
                frozen_pools = _source_must_hit(
                    must_hit_class,
                    _source_history(history, newest_first=False),
                )
                frozen_tickets = [sorted(frozen_pools[0])]
                port_pools = tuple(
                    list(pool)
                    for pool in (
                        port.metadata.source_candidate_number_pools
                    )
                )
                if frozen_pools != port_pools:
                    raise ParityError(
                        f"candidate-pool parity failed at {count}"
                    )
                candidate_pool_sha256 = hashlib.sha256(
                    _canonical_bytes(frozen_pools)
                ).hexdigest()
            if frozen_tickets != port_tickets:
                raise ParityError(
                    f"ticket parity failed: {method_id} at {count}"
                )
            cases.append(
                {
                    "candidate_pool_sha256": candidate_pool_sha256,
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
            "AST_COMPILE_FROZEN_FUNCTIONS_AND_COMPARE_CANONICAL_"
            "TICKETS_POSITIONAL_ORDER_DUPLICATES_AND_CANDIDATE_POOLS"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE11_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD
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
