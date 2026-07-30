#!/usr/bin/env python3
"""Verify wave-16 hot/co-occurrence output against frozen source text."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave16 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD,
    HOT_COOCCURRENCE_METHOD_ID,
    SOURCE_NATIVE_WAVE16_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD,
    LegacySourceNativeWave16Request,
    generate_legacy_source_native_wave16_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE16_PARITY_V1"
)
_CLASS_NAME = "HotCooccurrenceAnalyzer"
_CASE_HISTORY_COUNTS = (1, 10, 100, 2148)


class ParityError(ValueError):
    """Frozen source identity or port output differs."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _frozen_blob(
    frozen_root: Path,
    source_path: str,
) -> tuple[str, bytes]:
    completed = subprocess.run(
        (
            "git",
            "-C",
            str(frozen_root),
            "show",
            f"{FROZEN_SOURCE_COMMIT}:{source_path}",
        ),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ParityError(f"cannot read frozen source blob: {source_path}")
    oid = subprocess.run(
        (
            "git",
            "-C",
            str(frozen_root),
            "rev-parse",
            f"{FROZEN_SOURCE_COMMIT}:{source_path}",
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return oid, completed.stdout


def _load_frozen_class(
    *,
    source_text: str,
    source_identity: str,
    numpy_module: Any,
    pandas_module: Any,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == _CLASS_NAME
    ]
    if len(selected) != 1:
        raise ParityError("frozen hot/co-occurrence class missing")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "defaultdict": defaultdict,
        "Dict": dict,
        "List": list,
        "Optional": Optional,
        "Set": set,
        "Tuple": tuple,
        "__builtins__": __builtins__,
        "np": numpy_module,
        "pd": pandas_module,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return cast(type[Any], namespace[_CLASS_NAME])


def _source_ticket(
    *,
    analyzer_class: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], int]:
    instance = object.__new__(analyzer_class)
    instance.min_num = 1
    instance.max_num = 49
    instance.pick_count = 6
    source_history = [
        {
            "draw": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in history
    ]
    hot_frequency = instance.get_hot_numbers(
        source_history,
        window_size=50,
    )
    hot_numbers = [
        number for number, _count in hot_frequency[:20]
    ]
    cooccurrence = instance.build_cooccurrence_matrix(
        source_history,
        window_size=100,
    )
    recommended = instance.apply_cooccurrence_rules(
        hot_numbers,
        cooccurrence,
        pick_count=6,
        cooccurrence_weight=0.3,
    )
    return tuple(cast(list[int], recommended)), len(hot_numbers)


def verify_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    numpy_module = importlib.import_module("numpy")
    pandas_module = importlib.import_module("pandas")
    source_oid, source_raw = _frozen_blob(
        frozen_root,
        HOT_COOCCURRENCE_METHOD_ID,
    )
    source_sha256 = hashlib.sha256(source_raw).hexdigest()
    if source_sha256 != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE16_METHOD[
        HOT_COOCCURRENCE_METHOD_ID
    ]:
        raise ParityError("frozen hot/co-occurrence source identity changed")
    try:
        source_text = source_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParityError("frozen source is not UTF-8") from exc
    analyzer_class = _load_frozen_class(
        source_text=source_text,
        source_identity=HOT_COOCCURRENCE_METHOD_ID,
        numpy_module=numpy_module,
        pandas_module=pandas_module,
    )

    support_rows: list[dict[str, object]] = []
    for support_path, expected_sha256 in (
        FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE16_METHOD[
            HOT_COOCCURRENCE_METHOD_ID
        ]
    ):
        support_oid, support_raw = _frozen_blob(
            frozen_root,
            support_path,
        )
        actual_sha256 = hashlib.sha256(support_raw).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ParityError(f"frozen support changed: {support_path}")
        support_rows.append(
            {
                "source_blob_id": support_oid,
                "source_path": support_path,
                "source_sha256": actual_sha256,
            }
        )

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
    if len(all_history) <= max(_CASE_HISTORY_COUNTS):
        raise ParityError("pinned history is too short for parity cases")

    cases: list[dict[str, object]] = []
    for history_count in _CASE_HISTORY_COUNTS:
        history = all_history[:history_count]
        target = pinned.draws[history_count]
        source_ticket, source_candidate_k = _source_ticket(
            analyzer_class=analyzer_class,
            history=history,
        )
        port = generate_legacy_source_native_wave16_portfolio(
            LegacySourceNativeWave16Request(
                legacy_method_id=HOT_COOCCURRENCE_METHOD_ID,
                target_draw_number=target.draw_number,
                history=history,
            )
        )
        if port.tickets != (source_ticket,):
            raise ParityError(
                f"ticket parity failed at history_count={history_count}"
            )
        if port.metadata.source_candidate_k_values != (
            source_candidate_k,
        ):
            raise ParityError(
                f"candidate-K parity failed at history_count={history_count}"
            )
        cases.append(
            {
                "candidate_k": source_candidate_k,
                "history_count": history_count,
                "history_cutoff_draw_number": (
                    history[-1].draw_number
                ),
                "native_tickets": [list(source_ticket)],
                "target_draw_number": target.draw_number,
            }
        )

    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "method_id": HOT_COOCCURRENCE_METHOD_ID,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "runtime_dependency_versions": {
            "numpy": cast(str, numpy_module.__version__),
            "pandas": cast(str, pandas_module.__version__),
        },
        "source_blob_id": source_oid,
        "source_native_protocol": SOURCE_NATIVE_WAVE16_PROTOCOL,
        "source_sha256": source_sha256,
        "status": "PASS",
        "support_artifacts": support_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--expected-database-sha256",
        required=True,
    )
    parser.add_argument("--output-file", type=Path, required=True)
    args = parser.parse_args()
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
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
