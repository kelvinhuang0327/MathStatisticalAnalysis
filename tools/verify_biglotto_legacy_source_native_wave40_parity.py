#!/usr/bin/env python3
"""Verify wave-40 against the frozen 3+1 portfolio and support source."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave40 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD,
    PORTFOLIO_METHOD_ID,
    SOURCE_NATIVE_WAVE40_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD,
    LegacySourceNativeWave40Request,
    generate_legacy_source_native_wave40_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE40_PARITY_V1"
_HISTORY_COUNTS = tuple(range(100, 165))


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


def _behavior_facts(source_text: str) -> dict[str, object]:
    tree = ast.parse(source_text)
    methods = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_portfolio_backtest"
    ]
    if len(methods) != 1:
        raise ParityError("frozen portfolio entrypoint changed")
    compact = "".join(ast.unparse(methods[0]).split())
    required = (
        "cluster_pivot_3bet(history,max_num=49)",
        "core_bets[:3]",
        "cluster_pivot_hybrid(history,max_num=49,num_bets=1)",
        "ifaux_betnotinbets_portfolio:",
        "whilelen(bets_portfolio)<4:",
        "cluster_pivot_windowed(history,window=50,num_bets=1)",
        "ifw50andw50[0]notinbets_portfolio:",
        "bets_portfolio=bets_portfolio[:4]",
    )
    if any(marker not in compact for marker in required):
        raise ParityError("frozen 3+1 composition semantics changed")
    return {
        "auxiliary_duplicate_semantics": "SUPPRESS_EXACT_DUPLICATE",
        "core_ticket_count": 3,
        "fill_duplicate_semantics": "STOP_ON_EXACT_DUPLICATE",
        "fill_window": 50,
        "native_ticket_count_upper_bound": 4,
        "portfolio_order": "CORE_THREE_THEN_AUXILIARY_OR_WINDOW50_FILL",
        "source_history_cutoff": "STRICTLY_BEFORE_TARGET",
    }


def _support_functions(
    source_bytes: bytes,
) -> tuple[
    Callable[[list[dict[str, object]], int, int], list[list[int]]],
    Callable[..., list[list[int]]],
    Callable[..., list[list[int]]],
]:
    namespace: dict[str, object] = {
        "__file__": "tools/backtest_cluster_pivot_biglotto.py",
        "__name__": "frozen_wave40_cluster_support",
    }
    exec(
        compile(
            source_bytes,
            filename="tools/backtest_cluster_pivot_biglotto.py",
            mode="exec",
        ),
        namespace,
    )
    return (
        cast(
            Callable[
                [list[dict[str, object]], int, int],
                list[list[int]],
            ],
            namespace["cluster_pivot_3bet"],
        ),
        cast(
            Callable[..., list[list[int]]],
            namespace["cluster_pivot_hybrid"],
        ),
        cast(
            Callable[..., list[list[int]]],
            namespace["cluster_pivot_windowed"],
        ),
    )


def _reference_portfolio(
    *,
    history: list[dict[str, object]],
    cluster_three: Callable[[list[dict[str, object]], int, int], list[list[int]]],
    cluster_hybrid: Callable[..., list[list[int]]],
    cluster_windowed: Callable[..., list[list[int]]],
) -> tuple[tuple[int, ...], ...]:
    portfolio = cluster_three(history, 49, 6)[:3]
    auxiliary = cluster_hybrid(
        history,
        max_num=49,
        pick_count=6,
        num_bets=1,
    )
    if auxiliary and auxiliary[0] not in portfolio:
        portfolio.append(auxiliary[0])
    while len(portfolio) < 4:
        fill = cluster_windowed(
            history,
            window=50,
            max_num=49,
            pick_count=6,
            num_bets=1,
        )
        if fill and fill[0] not in portfolio:
            portfolio.append(fill[0])
        else:
            break
    return tuple(tuple(sorted(ticket)) for ticket in portfolio[:4])


def verify_wave40_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute the frozen support functions and compare positional tickets."""

    source_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{PORTFOLIO_METHOD_ID}",
    )
    source_sha256 = hashlib.sha256(source_raw).hexdigest()
    if source_sha256 != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE40_METHOD[PORTFOLIO_METHOD_ID]:
        raise ParityError("frozen wave-40 source SHA changed")
    behavior = _behavior_facts(source_raw.decode("utf-8"))

    support_artifacts: list[dict[str, str]] = []
    support_path, expected_support_sha256 = FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE40_METHOD[
        PORTFOLIO_METHOD_ID
    ][0]
    support_raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{support_path}",
    )
    support_sha256 = hashlib.sha256(support_raw).hexdigest()
    if support_sha256 != expected_support_sha256:
        raise ParityError("frozen wave-40 support SHA changed")
    support_artifacts.append({"path": support_path, "sha256": support_sha256})
    cluster_three, cluster_hybrid, cluster_windowed = _support_functions(support_raw)

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
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target = pinned.draws[history_count].draw_number
        source_rows: list[dict[str, object]] = [
            {
                "draw_number": draw.draw_number,
                "numbers": list(draw.numbers),
            }
            for draw in history
        ]
        reference = _reference_portfolio(
            history=source_rows,
            cluster_three=cluster_three,
            cluster_hybrid=cluster_hybrid,
            cluster_windowed=cluster_windowed,
        )
        port = generate_legacy_source_native_wave40_portfolio(
            LegacySourceNativeWave40Request(
                legacy_method_id=PORTFOLIO_METHOD_ID,
                target_draw_number=target,
                history=history,
            )
        )
        if reference != port.tickets:
            raise ParityError("frozen positional ticket parity failed")
        cases.append(
            {
                "history_draw_count": history_count,
                "native_duplicate_ticket_count": (port.metadata.native_duplicate_ticket_count),
                "native_ticket_count": len(port.tickets),
                "source_duplicate_suppression_results": list(
                    port.metadata.source_duplicate_suppression_results
                ),
                "status": "PASS",
                "target_draw_number": target,
                "tickets": [list(ticket) for ticket in port.tickets],
            }
        )
    document: dict[str, object] = {
        "case_count": len(cases),
        "cases": cases,
        "dataset_sha256": pinned.database_sha256_before,
        "frozen_source_behavior_facts": behavior,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "source_artifacts": [
            {
                "path": PORTFOLIO_METHOD_ID,
                "sha256": source_sha256,
            }
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE40_PROTOCOL,
        "status": "PASS",
        "support_artifacts": support_artifacts,
    }
    document["parity_sha256"] = hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--output-file", required=True, type=Path)
    args = parser.parse_args()
    if args.output_file.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output_file}")
    document = verify_wave40_parity(
        frozen_root=args.frozen_root,
        database=args.database,
        expected_database_sha256=args.expected_database_sha256,
    )
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_bytes(_canonical_bytes(document) + b"\n")
    print(
        json.dumps(
            {
                "case_count": document["case_count"],
                "output_file": str(args.output_file),
                "parity_sha256": document["parity_sha256"],
                "status": document["status"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
