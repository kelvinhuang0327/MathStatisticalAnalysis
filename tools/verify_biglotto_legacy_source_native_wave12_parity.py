#!/usr/bin/env python3
"""Verify wave-12 port against functions compiled from frozen source text."""

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
from lottolab.application.legacy_source_native_portfolios_wave12 import (
    MODERATE_SELECTION_METHOD_ID,
    SOURCE_NATIVE_WAVE12_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD,
    LegacySourceNativeWave12Request,
    generate_legacy_source_native_wave12_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE12_PARITY_V1"
)
_FUNCTION_NAMES = {
    "calculate_gaps",
    "calculate_frequency",
    "moderate_selection_with_params",
}
_HISTORY_COUNTS = (50, 300, 2148)
_PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
_HOT_RANK_MINS = (3, 4, 5, 6)
_COLD_GAP_RANGES = ((6, 10), (7, 11), (8, 12), (9, 13), (10, 14))


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _frozen_source(frozen_root: Path) -> tuple[str, bytes]:
    completed = subprocess.run(
        (
            "git",
            "-C",
            str(frozen_root),
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{MODERATE_SELECTION_METHOD_ID}",
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


def _load_functions(
    source_text: str,
    source_identity: str,
) -> dict[str, Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in _FUNCTION_NAMES
    ]
    found = {
        node.name
        for node in selected
        if isinstance(node, ast.FunctionDef)
    }
    if found != _FUNCTION_NAMES:
        raise ParityError(
            f"frozen functions missing: {sorted(_FUNCTION_NAMES - found)}"
        )
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "__builtins__": __builtins__,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return namespace


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
    namespace: dict[str, Any],
    history: list[dict[str, object]],
) -> list[list[int]]:
    selector = namespace["moderate_selection_with_params"]
    tickets: list[list[int]] = []
    for penalty in _PENALTIES:
        for hot_rank_min in _HOT_RANK_MINS:
            for cold_min, cold_max in _COLD_GAP_RANGES:
                for bet_index in range(2):
                    adjusted_penalty = penalty * (
                        1 + bet_index * 0.1
                    )
                    tickets.append(
                        selector(
                            history,
                            49,
                            6,
                            last_draw_penalty=min(
                                adjusted_penalty,
                                0.5,
                            ),
                            hot_rank_min=(
                                hot_rank_min + bet_index * 2
                            ),
                            hot_rank_max=15,
                            cold_gap_min=cold_min,
                            cold_gap_max=cold_max,
                        )
                    )
    return tickets


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
    source_text, source_raw = _frozen_source(frozen_root)
    if hashlib.sha256(source_raw).hexdigest() != (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
    ):
        raise ParityError("frozen source SHA changed")
    namespace = _load_functions(
        source_text,
        f"{FROZEN_SOURCE_COMMIT}:{MODERATE_SELECTION_METHOD_ID}",
    )

    cases: list[dict[str, object]] = []
    for count in _HISTORY_COUNTS:
        history = all_history[:count]
        frozen_tickets = _source_tickets(
            namespace,
            _source_history(history),
        )
        port = generate_legacy_source_native_wave12_portfolio(
            LegacySourceNativeWave12Request(
                legacy_method_id=MODERATE_SELECTION_METHOD_ID,
                target_draw_number=f"parity-after-{count}",
                history=history,
            )
        )
        port_tickets = [list(ticket) for ticket in port.tickets]
        if frozen_tickets != port_tickets:
            raise ParityError(f"ticket parity failed at {count}")
        cases.append(
            {
                "history_draw_count": count,
                "legacy_method_id": MODERATE_SELECTION_METHOD_ID,
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
            "AST_COMPILE_FROZEN_FUNCTIONS_AND_COMPARE_180_GRID_"
            "CONFIGURATIONS_360_POSITIONAL_TICKETS_AND_DUPLICATES"
        ),
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "port_protocol": SOURCE_NATIVE_WAVE12_PROTOCOL,
        "source_sha256": dict(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD
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
