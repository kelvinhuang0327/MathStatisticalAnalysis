#!/usr/bin/env python3
"""Verify wave-34 port against the frozen AutoOptimizer class AST."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_frozen_unified_core import (
    frozen_bayesian_ticket,
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_trend_ticket,
    frozen_zone_balance_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave34 import (
    AUTO_OPTIMIZER_METHOD_ID,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD,
    METHOD_NAMES,
    SOURCE_NATIVE_WAVE34_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD,
    VARIANT_CONFIGURATIONS,
    WINDOWS,
    LegacySourceNativeWave34Request,
    generate_legacy_source_native_wave34_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE34_PARITY_V1"
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


def _history(
    rows: list[dict[str, object]],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=cast(str, row["draw"]),
            numbers=cast(
                tuple[int, int, int, int, int, int],
                row["numbers"],
            ),
        )
        for row in rows
    )


class _FrozenEngineReference:
    def zone_balance_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {
            "numbers": list(frozen_zone_balance_ticket(_history(history)))
        }

    def bayesian_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {"numbers": list(frozen_bayesian_ticket(_history(history)))}

    def trend_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {"numbers": list(frozen_trend_ticket(_history(history)))}

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {"numbers": list(frozen_frequency_ticket(_history(history)))}

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return {"numbers": list(frozen_deviation_ticket(_history(history)))}


@dataclass(slots=True)
class _StrategyAdapter:
    name: str
    predict_func: Callable[
        [list[dict[str, object]], dict[str, int]],
        dict[str, object],
    ]
    optimal_window: int


def _frozen_strategy_space(
    source_text: str,
    engine: _FrozenEngineReference,
) -> list[_StrategyAdapter]:
    tree = ast.parse(source_text)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AutoOptimizer"
    ]
    if len(classes) != 1:
        raise ParityError("frozen AutoOptimizer class changed")
    namespace: dict[str, object] = {
        "StrategyAdapter": _StrategyAdapter,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[classes[0]], type_ignores=[])
            ),
            filename=AUTO_OPTIMIZER_METHOD_ID,
            mode="exec",
        ),
        namespace,
    )
    class_object = cast(type[Any], namespace["AutoOptimizer"])
    instance = object.__new__(class_object)
    instance.engine = engine
    result = instance.generate_strategy_space()
    return cast(list[_StrategyAdapter], result)


def _behavior_facts(source_text: str) -> dict[str, object]:
    tree = ast.parse(source_text)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AutoOptimizer"
    ]
    if len(classes) != 1:
        raise ParityError("frozen AutoOptimizer class changed")
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef)
        and node.name == "generate_strategy_space"
    ]
    if len(methods) != 1:
        raise ParityError("frozen strategy-space method changed")
    assignments: dict[str, object] = {}
    for node in ast.walk(methods[0]):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"methods", "windows"}
        ):
            assignments[node.targets[0].id] = ast.literal_eval(node.value)
    if (
        tuple(cast(list[str], assignments.get("methods"))) != METHOD_NAMES
        or tuple(cast(list[int], assignments.get("windows"))) != WINDOWS
    ):
        raise ParityError("frozen method/window grid changed")
    compact = "".join(ast.unparse(methods[0]).split())
    if (
        "getattr(self.engine,m_name)(hist[-w_size:],rules)"
        not in compact
        or "optimal_window=window" not in compact
    ):
        raise ParityError("frozen adapter slicing semantics changed")
    return {
        "configuration_count": 25,
        "method_order": list(METHOD_NAMES),
        "native_ticket_count": 25,
        "variant_slice": "TRAILING_WINDOW_STRICTLY_BEFORE_TARGET",
        "window_order": list(WINDOWS),
    }


def _history_dicts(
    history: tuple[LegacyHistoryDraw, ...],
) -> list[dict[str, object]]:
    return [
        {
            "draw": draw.draw_number,
            "numbers": draw.numbers,
        }
        for draw in history
    ]


def verify_wave34_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute frozen adapters and compare all 25 positional tickets."""

    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{AUTO_OPTIMIZER_METHOD_ID}",
    )
    source_sha256 = hashlib.sha256(raw).hexdigest()
    if (
        source_sha256
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE34_METHOD[
            AUTO_OPTIMIZER_METHOD_ID
        ]
    ):
        raise ParityError("frozen wave-34 source SHA changed")
    source_text = raw.decode("utf-8")
    behavior = _behavior_facts(source_text)
    adapters = _frozen_strategy_space(
        source_text,
        _FrozenEngineReference(),
    )
    if (
        len(adapters) != 25
        or tuple(
            (
                f"{method_name.removesuffix('_predict')}_{window}",
                window,
            )
            for method_name, window in VARIANT_CONFIGURATIONS
        )
        != tuple(
            (adapter.name, adapter.optimal_window)
            for adapter in adapters
        )
    ):
        raise ParityError("frozen adapter order changed")
    support_artifacts: list[dict[str, str]] = []
    for path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE34_METHOD[
            AUTO_OPTIMIZER_METHOD_ID
        ]
    ):
        support_raw = _git(
            frozen_root,
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{path}",
        )
        digest = hashlib.sha256(support_raw).hexdigest()
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
    rules = {"minNumber": 1, "maxNumber": 49, "pickCount": 6}
    cases: list[dict[str, object]] = []
    for history_count in _HISTORY_COUNTS:
        history = all_history[:history_count]
        target = (
            pinned.draws[history_count].draw_number
            if history_count < len(pinned.draws)
            else f"AFTER_{history[-1].draw_number}"
        )
        rows = _history_dicts(history)
        reference = tuple(
            tuple(cast(list[int], adapter.predict_func(rows, rules)["numbers"]))
            for adapter in adapters
        )
        port = generate_legacy_source_native_wave34_portfolio(
            LegacySourceNativeWave34Request(
                legacy_method_id=AUTO_OPTIMIZER_METHOD_ID,
                target_draw_number=target,
                history=history,
            )
        )
        if reference != port.tickets:
            raise ParityError("frozen positional ticket parity failed")
        cases.append(
            {
                "history_draw_count": history_count,
                "native_duplicate_ticket_count": (
                    port.metadata.native_duplicate_ticket_count
                ),
                "status": "PASS",
                "target_draw_number": target,
                "tickets": [
                    list(ticket) for ticket in port.tickets
                ],
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
                "path": AUTO_OPTIMIZER_METHOD_ID,
                "sha256": source_sha256,
            }
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE34_PROTOCOL,
        "status": "PASS",
        "support_artifacts": support_artifacts,
    }
    document["parity_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


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
    document = verify_wave34_parity(
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
