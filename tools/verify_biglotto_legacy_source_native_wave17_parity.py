#!/usr/bin/env python3
"""Verify wave-17 random-backed outputs against frozen source classes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import random
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave17 import (
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD,
    SCIENTIFIC_SMART_RANDOM_METHOD_ID,
    SMART_MULTI_BET_METHOD_ID,
    SOURCE_NATIVE_WAVE17_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD,
    LegacySourceNativeWave17Request,
    generate_legacy_source_native_wave17_portfolio,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    load_pinned_biglotto_history,
)

FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PARITY_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE17_PARITY_V1"
)
_MAIN_OPTIMIZER_PATH = "lottery_api/models/main_optimizer.py"
_CLASS_BY_METHOD = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: "MainZoneSmartOptimizer",
    SMART_MULTI_BET_METHOD_ID: "SmartMultiBetSystem",
}
_CASE_HISTORY_COUNTS = (1, 20, 300, 2148)


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
    class_name: str,
    random_module: random.Random,
    numpy_module: Any,
) -> type[Any]:
    tree = ast.parse(source_text, filename=source_identity)
    selected: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(selected) != 1:
        raise ParityError(f"frozen class missing: {class_name}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {
        "Counter": Counter,
        "Dict": dict,
        "List": list,
        "Set": set,
        "Tuple": tuple,
        "__builtins__": __builtins__,
        "np": numpy_module,
        "random": random_module,
    }
    exec(compile(module, source_identity, "exec"), namespace)
    return cast(type[Any], namespace[class_name])


def _source_scientific_tickets(
    *,
    optimizer_class: type[Any],
) -> tuple[tuple[int, ...], ...]:
    optimizer = optimizer_class(
        {
            "minNumber": 1,
            "maxNumber": 49,
            "pickCount": 6,
        }
    )
    tickets = optimizer.generate_smart_bets(count=7)
    return tuple(tuple(cast(list[int], ticket)) for ticket in tickets)


def _source_smart_multi(
    *,
    system_class: type[Any],
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    recent_first = tuple(reversed(history[-300:]))
    source_history = [
        {
            "draw_id": draw.draw_number,
            "numbers": list(draw.numbers),
        }
        for draw in recent_first
    ]
    system = system_class()
    pool = system._build_candidate_pool(source_history, 1, 49)
    result = system.generate_smart_bets(
        source_history,
        {
            "pick_count": 6,
            "min_number": 1,
            "max_number": 49,
            "has_special": True,
        },
        6,
    )
    tickets = tuple(
        tuple(cast(list[int], row["numbers"]))
        for row in cast(list[dict[str, object]], result["bets"])
    )
    counts = tuple(
        len(cast(dict[str, list[int]], pool)[key])
        for key in (
            "hot",
            "cold",
            "mid",
            "recent_active",
            "last_draw",
            "comeback",
        )
    )
    return tickets, counts


def verify_parity(
    *,
    frozen_root: Path,
    database: Path,
    expected_database_sha256: str,
) -> dict[str, object]:
    numpy_module = importlib.import_module("numpy")
    source_rows: list[dict[str, object]] = []
    source_raw_by_method: dict[str, bytes] = {}
    for method_id in (
        SCIENTIFIC_SMART_RANDOM_METHOD_ID,
        SMART_MULTI_BET_METHOD_ID,
    ):
        source_oid, source_raw = _frozen_blob(frozen_root, method_id)
        source_sha256 = hashlib.sha256(source_raw).hexdigest()
        if (
            source_sha256
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[method_id]
        ):
            raise ParityError(f"frozen source identity changed: {method_id}")
        source_raw_by_method[method_id] = source_raw
        source_rows.append(
            {
                "source_blob_id": source_oid,
                "source_path": method_id,
                "source_sha256": source_sha256,
            }
        )

    support_rows: list[dict[str, object]] = []
    support_paths = {
        item
        for rows in (
            FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD.values()
        )
        for item in rows
    }
    support_raw_by_path: dict[str, bytes] = {}
    for support_path, expected_sha256 in sorted(support_paths):
        support_oid, support_raw = _frozen_blob(
            frozen_root,
            support_path,
        )
        actual_sha256 = hashlib.sha256(support_raw).hexdigest()
        if actual_sha256 != expected_sha256:
            raise ParityError(f"frozen support changed: {support_path}")
        support_raw_by_path[support_path] = support_raw
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
        require_replay_authority=False,
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
    for method_id in (
        SCIENTIFIC_SMART_RANDOM_METHOD_ID,
        SMART_MULTI_BET_METHOD_ID,
    ):
        class_source_path = (
            _MAIN_OPTIMIZER_PATH
            if method_id == SCIENTIFIC_SMART_RANDOM_METHOD_ID
            else method_id
        )
        try:
            class_source_text = (
                support_raw_by_path[class_source_path]
                if class_source_path in support_raw_by_path
                else source_raw_by_method[class_source_path]
            ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParityError("frozen class source is not UTF-8") from exc

        for history_count in _CASE_HISTORY_COUNTS:
            history = all_history[:history_count]
            target = pinned.draws[history_count]
            port = generate_legacy_source_native_wave17_portfolio(
                LegacySourceNativeWave17Request(
                    legacy_method_id=method_id,
                    target_draw_number=target.draw_number,
                    history=history,
                )
            )
            frozen_random = random.Random()
            frozen_random.seed(port.metadata.seed_integer, version=2)
            source_class = _load_frozen_class(
                source_text=class_source_text,
                source_identity=class_source_path,
                class_name=_CLASS_BY_METHOD[method_id],
                random_module=frozen_random,
                numpy_module=numpy_module,
            )
            if method_id == SCIENTIFIC_SMART_RANDOM_METHOD_ID:
                source_tickets = _source_scientific_tickets(
                    optimizer_class=source_class
                )
                source_candidate_counts: tuple[int, ...] = ()
            else:
                source_tickets, source_candidate_counts = (
                    _source_smart_multi(
                        system_class=source_class,
                        history=history,
                    )
                )
            if port.tickets != source_tickets:
                raise ParityError(
                    f"ticket parity failed: {method_id}, "
                    f"history_count={history_count}"
                )
            if (
                port.metadata.source_candidate_ticket_counts
                != source_candidate_counts
            ):
                raise ParityError(
                    f"candidate-pool parity failed: {method_id}, "
                    f"history_count={history_count}"
                )
            cases.append(
                {
                    "candidate_pool_counts": list(
                        source_candidate_counts
                    ),
                    "history_count": history_count,
                    "history_cutoff_draw_number": (
                        history[-1].draw_number
                    ),
                    "legacy_method_id": method_id,
                    "native_tickets": [
                        list(ticket) for ticket in source_tickets
                    ],
                    "seed_digest": port.metadata.seed_digest,
                    "target_draw_number": target.draw_number,
                }
            )

    return {
        "case_count": len(cases),
        "cases": cases,
        "database_sha256": pinned.database_sha256_before,
        "frozen_source_commit": FROZEN_SOURCE_COMMIT,
        "parity_schema_version": PARITY_SCHEMA_VERSION,
        "runtime_dependency_versions": {
            "numpy": cast(str, numpy_module.__version__),
        },
        "source_artifacts": source_rows,
        "source_native_protocol": SOURCE_NATIVE_WAVE17_PROTOCOL,
        "status": "PASS",
        "support_artifacts": support_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--expected-database-sha256", required=True)
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
