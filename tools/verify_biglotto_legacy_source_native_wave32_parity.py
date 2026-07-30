#!/usr/bin/env python3
"""Verify wave-32 port against the frozen high-level research function."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
import random
import subprocess
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_frozen_unified_core import (
    frozen_deviation_ticket,
    frozen_frequency_ticket,
    frozen_markov_ticket,
    frozen_statistical_ticket,
    frozen_zone_balance_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave32 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_NATIVE_WAVE32_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD,
    VARIANT_CONFIGURATIONS,
    VARIANT_HISTORY_METHOD_ID,
    LegacySourceNativeWave32Request,
    generate_legacy_source_native_wave32_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE32_PARITY_V1"
)
_DATASET_PREFIX_COUNTS = (140, 220, 520, 2149)


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


def _reference_ticket(
    method_name: str,
    rows: list[dict[str, object]],
) -> tuple[int, ...]:
    history = _history(rows)
    if method_name == "deviation_predict":
        return frozen_deviation_ticket(history)
    if method_name == "statistical_predict":
        try:
            return frozen_statistical_ticket(history)[0]
        except ValueError as exc:
            if str(exc) != "FROZEN_STATISTICAL_FREQUENCY_FALLBACK_REQUIRED":
                raise
            return frozen_frequency_ticket(history)
    if method_name == "markov_predict":
        return frozen_markov_ticket(history)[0]
    if method_name == "frequency_predict":
        return frozen_frequency_ticket(history)
    if method_name == "zone_balance_predict":
        return frozen_zone_balance_ticket(history)
    raise ParityError("frozen source called an unexpected predictor")


class _RecordingEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], tuple[int, ...]]] = []

    def _call(
        self,
        method_name: str,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        ticket = _reference_ticket(method_name, history)
        self.calls.append(
            (
                method_name,
                tuple(cast(str, row["draw"]) for row in history),
                ticket,
            )
        )
        return {"numbers": list(ticket)}

    def deviation_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._call("deviation_predict", history)

    def statistical_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._call("statistical_predict", history)

    def markov_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._call("markov_predict", history)

    def frequency_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._call("frequency_predict", history)

    def zone_balance_predict(
        self,
        history: list[dict[str, object]],
        _rules: dict[str, int],
    ) -> dict[str, object]:
        return self._call("zone_balance_predict", history)


class _Database:
    def __init__(self, newest_first: list[dict[str, object]]) -> None:
        self.newest_first = newest_first

    def get_all_draws(
        self,
        *,
        lottery_type: str,
    ) -> list[dict[str, object]]:
        if lottery_type != "BIG_LOTTO":
            raise ParityError("frozen source lottery type changed")
        return self.newest_first


def _frozen_function(
    source_text: str,
    *,
    database: _Database,
    engine: _RecordingEngine,
) -> Any:
    tree = ast.parse(source_text)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "analyze_variants"
    ]
    if len(functions) != 1:
        raise ParityError("frozen analyze_variants function changed")

    def database_factory(**_kwargs: object) -> _Database:
        return database

    def rules_factory(_lottery_type: object) -> dict[str, int]:
        return {
            "minNumber": 1,
            "maxNumber": 49,
            "pickCount": 6,
        }

    namespace: dict[str, object] = {
        "DatabaseManager": database_factory,
        "UnifiedPredictionEngine": lambda: engine,
        "get_lottery_rules": rules_factory,
        "os": os,
        "project_root": "/frozen",
        "random": random,
    }
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[functions[0]], type_ignores=[])
            ),
            filename=VARIANT_HISTORY_METHOD_ID,
            mode="exec",
        ),
        namespace,
    )
    return namespace["analyze_variants"]


def _behavior_facts(source_text: str) -> dict[str, object]:
    tree = ast.parse(source_text)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "analyze_variants"
    ]
    if len(functions) != 1:
        raise ParityError("frozen analyze_variants function changed")
    assignments = [
        node
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "variants"
            for target in node.targets
        )
    ]
    if len(assignments) != 1:
        raise ParityError("frozen variants assignment changed")
    variants = ast.literal_eval(assignments[0].value)
    if tuple(tuple(item) for item in variants) != VARIANT_CONFIGURATIONS:
        raise ParityError("frozen variant order changed")
    source_compact = "".join(source_text.split())
    for fragment in (
        "list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))",
        "start_hist=max(0,target_idx-windowit)",
        "hist_variant=all_draws[start_hist:target_idx]",
        "iflen(hist_variant)<20:continue",
        "predicted=set(res['numbers'][:6])",
    ):
        if "".join(fragment.split()) not in source_compact:
            raise ParityError("frozen causal wrapper semantics changed")
    return {
        "minimum_history_draws": 20,
        "native_variant_count": 11,
        "source_database_order_transform": (
            "NEWEST_FIRST_REVERSED_TO_OLDEST_FIRST"
        ),
        "variant_configurations": [
            [method_name, window]
            for method_name, window in VARIANT_CONFIGURATIONS
        ],
        "variant_slice": "TRAILING_WINDOW_STRICTLY_BEFORE_TARGET",
    }


def verify_wave32_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    """Execute the frozen wrapper and compare all eleven positional tickets."""

    raw = _git(
        frozen_root,
        "show",
        f"{FROZEN_SOURCE_COMMIT}:{VARIANT_HISTORY_METHOD_ID}",
    )
    source_sha256 = hashlib.sha256(raw).hexdigest()
    if (
        source_sha256
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[
            VARIANT_HISTORY_METHOD_ID
        ]
    ):
        raise ParityError("frozen wave-32 source SHA changed")
    source_text = raw.decode("utf-8")
    behavior = _behavior_facts(source_text)
    support_artifacts: list[dict[str, str]] = []
    for path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD[
            VARIANT_HISTORY_METHOD_ID
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
    )
    all_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned.draws
    )
    cases: list[dict[str, object]] = []
    for prefix_count in _DATASET_PREFIX_COUNTS:
        prefix = all_history[:prefix_count]
        newest_first: list[dict[str, object]] = [
            {
                "date": "",
                "draw": draw.draw_number,
                "numbers": draw.numbers,
            }
            for draw in reversed(prefix)
        ]
        engine = _RecordingEngine()
        frozen = _frozen_function(
            source_text,
            database=_Database(newest_first),
            engine=engine,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            frozen()
        if len(engine.calls) != 120 * len(VARIANT_CONFIGURATIONS):
            raise ParityError("frozen wrapper call count changed")
        for target_offset in range(120):
            target_index = prefix_count - 120 + target_offset
            target = prefix[target_index]
            prior = prefix[:target_index]
            port = generate_legacy_source_native_wave32_portfolio(
                LegacySourceNativeWave32Request(
                    legacy_method_id=VARIANT_HISTORY_METHOD_ID,
                    target_draw_number=target.draw_number,
                    history=prior,
                )
            )
            start = target_offset * len(VARIANT_CONFIGURATIONS)
            calls = engine.calls[
                start : start + len(VARIANT_CONFIGURATIONS)
            ]
            reference_tickets = tuple(call[2] for call in calls)
            if reference_tickets != port.tickets:
                raise ParityError("frozen positional ticket parity failed")
            for call, (method_name, window) in zip(
                calls,
                VARIANT_CONFIGURATIONS,
                strict=True,
            ):
                if (
                    call[0] != method_name
                    or call[1]
                    != tuple(
                        draw.draw_number for draw in prior[-window:]
                    )
                ):
                    raise ParityError(
                        "frozen method or causal window parity failed"
                    )
            cases.append(
                {
                    "dataset_prefix_draw_count": prefix_count,
                    "history_draw_count": len(prior),
                    "native_duplicate_ticket_count": (
                        port.metadata.native_duplicate_ticket_count
                    ),
                    "status": "PASS",
                    "target_draw_number": target.draw_number,
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
                "path": VARIANT_HISTORY_METHOD_ID,
                "sha256": source_sha256,
            }
        ],
        "source_native_protocol": SOURCE_NATIVE_WAVE32_PROTOCOL,
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
    document = verify_wave32_parity(
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
